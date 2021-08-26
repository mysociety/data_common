import base64
from urllib.request import urlopen
from selenium.common.exceptions import NoSuchElementException
from typing import Any, Dict, IO, Iterable, Optional, Set, Type, Union
from altair_saver.types import JSONDict, Mimebundle
from altair_saver._utils import extract_format, infer_mode_from_spec

from altair_saver.savers._selenium import (CDN_URL, EXTRACT_CODE,
                                           HTML_TEMPLATE, JavascriptError,
                                           MimebundleContent, SeleniumSaver,
                                           get_bundled_script)

import altair as alt


def get_as_base64(url):
    """
    open image and get as base64 byte-string
    """
    return base64.b64encode(urlopen(url).read())


HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
  <title>Embedding Vega-Lite</title>
  <script src="https://ajax.googleapis.com/ajax/libs/webfont/1.6.26/webfont.js"></script>
  <script src="{vega_url}"></script>
  <script src="{vegalite_url}"></script>
  <script src="{vegaembed_url}"></script>
</head>
<body>
  <div id="vis"></div>
</body>
</html>
"""

EXTRACT_CODE = """
let spec = arguments[0];
const embedOpt = arguments[1];
const format = arguments[2];
const done = arguments[3];

const base64logo = "$$BASE64LOGO$$";

function load_chart() {
    vegaEmbed('#vis', spec, embedOpt).then(function(result) {
                if (format === 'png') {
                    result.view
                        .toCanvas(embedOpt.scaleFactor || 1)
                        .then(function(canvas){return canvas.toDataURL('image/png');})
                        .then(result => add_footer(result))
                        .catch(function(err) {
                            console.error(err);
                            done({error: err.toString()});
                        });
};
})
}


function getImageDimensions(file) {
  return new Promise (function (resolved, rejected) {
    var i = new Image()
    i.onload = function(){
      resolved({w: i.width, h: i.height})
    };
    i.src = file
  })
}

async function add_footer(base64data) {


    data_source = embedOpt.caption || ""
    logo = embedOpt.logo || false

    if (logo == false && data_source == ""){
        done({result: base64data})
    }

    dims = await getImageDimensions(base64data)

    scaleFactor = embedOpt.scaleFactor || 1
    footer = embedOpt.footerHeight || 50;
    width = dims.w || 600;
    height = dims.h || 300;
    footer = footer * scaleFactor;
    height = height + footer;

    new_canvas = document.createElement("CANVAS");
    document.body.appendChild(new_canvas)

    new_canvas.style.width = width  + "px";
    new_canvas.style.height = height  + "px";
    new_canvas.width = width;
    new_canvas.height = height;
    ctx = new_canvas.getContext('2d');
    ctx.fillStyle = 'white';
    ctx.fillRect(0,0,new_canvas.width, new_canvas.height);

    font_size = 12 * scaleFactor;
    caption_offset = 7.5 * scaleFactor;
    ctx.font = font_size + "px Source Sans Pro";
    ctx.fillStyle = 'black';
    text_width = ctx.measureText(data_source + "   ").width;
    text_height = ctx.measureText('M').width;
    ctx.fillText(data_source, new_canvas.width - text_width,
                 new_canvas.height - caption_offset);

    var img_logo = new Image();
    document.body.appendChild(img_logo)
    img_logo.onload = function() {
        ratio = this.height / this.width;
        length = width * 0.2;
        height = length * ratio;
        if (logo == true){
            ctx.drawImage(this, 0, new_canvas.height - height, length, height);
        }
        final_data = new_canvas.toDataURL('image/png', 1)
        done({result: final_data})
        }

    var img = new Image();
    document.body.appendChild(img)
    img.onload = function() {
        ctx.drawImage(this, 0, 0);
        img_logo.src = base64logo;
    };
    img.src = base64data;

}

WebFont.load({
            google: {
            families: ['Source Sans Pro:400']
            },
    active: load_chart
    })

"""


class MSSaver(SeleniumSaver):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._logo = None

    def _get_logo(self):
        if self._logo is None:
            self._logo = "data:image/jpg;base64," + get_as_base64(
                "https://research.mysociety.org/sites/foi-monitor/static/img/mysociety-logo.jpg").decode()
        return self._logo

    def _extract(self, fmt: str) -> MimebundleContent:
        driver = self._registry.get(self._webdriver, self._driver_timeout)

        if self._offline:
            js_resources = {
                "vega.js": get_bundled_script("vega", self._package_versions["vega"]),
                "vega-lite.js": get_bundled_script(
                    "vega-lite", self._package_versions["vega-lite"]
                ),
                "vega-embed.js": get_bundled_script(
                    "vega-embed", self._package_versions["vega-embed"]
                ),
            }
            html = HTML_TEMPLATE.format(
                vega_url="/vega.js",
                vegalite_url="/vega-lite.js",
                vegaembed_url="/vega-embed.js",
            )
        else:
            js_resources = {}
            html = HTML_TEMPLATE.format(
                vega_url=CDN_URL.format(
                    package="vega", version=self._package_versions["vega"]
                ),
                vegalite_url=CDN_URL.format(
                    package="vega-lite", version=self._package_versions["vega-lite"]
                ),
                vegaembed_url=CDN_URL.format(
                    package="vega-embed", version=self._package_versions["vega-embed"]
                ),
            )

        url = self._serve(html, js_resources)
        driver.get("about:blank")
        driver.get(url)
        try:
            driver.find_element_by_id("vis")
        except NoSuchElementException:
            raise RuntimeError(f"Could not load {url}")
        if not self._offline:
            online = driver.execute_script("return navigator.onLine")
            if not online:
                raise RuntimeError(
                    f"Internet connection required for saving chart as {fmt} with offline=False."
                )
        opt = self._embed_options.copy()
        opt["mode"] = self._mode

        extract_code = EXTRACT_CODE.replace("$$BASE64LOGO$$", str(self._get_logo()))
        result = driver.execute_async_script(
            extract_code, self._spec, opt, fmt)
        if "error" in result:
            raise JavascriptError(result["error"])
        return result["result"]


def render(
    chart: Union[alt.TopLevelMixin, JSONDict],
    fmts: Union[str, Iterable[str]] = "png",
    mode: Optional[str] = None,
    embed_options: Optional[JSONDict] = None,
    **kwargs: Any,
) -> Mimebundle:

    if isinstance(fmts, str):
        fmts = [fmts]
    mimebundle: Mimebundle = {}

    spec: JSONDict = {}
    if isinstance(chart, dict):
        spec = chart
    else:
        spec = chart.to_dict()

    if mode is None:
        mode = infer_mode_from_spec(spec)

    if embed_options is None:
        embed_options = alt.renderers.options.get("embed_options", None)

    for fmt in fmts:
        Saver = MSSaver
        saver = Saver(spec, mode=mode, embed_options=embed_options, **kwargs)
        mimebundle.update(saver.mimebundle(fmt))

    return mimebundle
