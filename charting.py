import base64
from urllib.request import urlopen

import altair as alt
from altair_saver import save as altair_save_chart
import altair_saver.savers._selenium
from altair_saver.savers._selenium import (CDN_URL, EXTRACT_CODE,
                                           HTML_TEMPLATE, JavascriptError,
                                           MimebundleContent, SeleniumSaver,
                                           get_bundled_script)
from selenium.common.exceptions import NoSuchElementException

from . import altair_theme
from pathlib import Path


def save_chart(chart, filename, scale_factor=1, **kwargs):
    """
        dumbed down version of altair save function that just assumes
        we're sending extra properties to the embed options
    """
    if isinstance(filename, Path):
        # altair doesn't process paths right
        filename = str(filename)
    altair_save_chart(
        chart, filename, scale_factor=scale_factor, embed_options=kwargs)


"""
update html template and extract code used to add reference to font
"""


def get_as_base64(url):
    """
    open image and get as base64 byte-string
    """
    return base64.b64encode(urlopen(url).read())


logo_base_64 = "data:image/jpg;base64," + get_as_base64(
    "https://research.mysociety.org/sites/foi-monitor/static/img/mysociety-logo.jpg").decode()

altair_saver.savers._selenium.HTML_TEMPLATE = """
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
    ctx.fillText(data_source, new_canvas.width - text_width, new_canvas.height - caption_offset);

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

# load logo straight in
altair_saver.savers._selenium.EXTRACT_CODE = EXTRACT_CODE.replace(
    "$$BASE64LOGO$$", str(logo_base_64))


def enable_altair():
    # do basic config for altair
    # register the custom theme under a chosen name
    alt.themes.register('mysoc_theme', lambda: altair_theme.mysoc_theme)
    # enable the newly registered theme
    alt.themes.enable('mysoc_theme')
    alt.renderers.enable("png")
