import altair as alt
from . import altair_theme

import altair_saver.savers._selenium
from altair_saver.savers._selenium import (
    SeleniumSaver, JavascriptError, get_bundled_script,
    MimebundleContent, CDN_URL, HTML_TEMPLATE, EXTRACT_CODE)
from selenium.common.exceptions import NoSuchElementException

"""
update html template and extract code used to add reference to font
"""

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

altair_saver.savers._selenium.EXTRACT_CODE = """
let spec = arguments[0];
const embedOpt = arguments[1];
const format = arguments[2];
const done = arguments[3];


load_chart = function() {
    if (format === 'vega') {
        if (embedOpt.mode === 'vega-lite') {
            vegaLite = (typeof vegaLite === "undefined") ? vl : vegaLite;
            try {
                const compiled = vegaLite.compile(spec);
                spec = compiled.spec;
            } catch(error) {
                done({error: error.toString()})
            }
        }
        done({result: spec});
    }
        vegaEmbed('#vis', spec, embedOpt).then(function(result) {
            if (format === 'png') {
                result.view
                    .toCanvas(embedOpt.scaleFactor || 1)
                    .then(function(canvas){return canvas.toDataURL('image/png');})
                    .then(result => done({result}))
                    .catch(function(err) {
                        console.error(err);
                        done({error: err.toString()});
                    });
            } else if (format === 'svg') {
                result.view
                    .toSVG(embedOpt.scaleFactor || 1)
                    .then(result => done({result}))
                    .catch(function(err) {
                        console.error(err);
                        done({error: err.toString()});
                    });
            } else {
                const error = "Unrecognized format: " + format;
                console.error(error);
                done({error});
            }
        }).catch(function(err) {
            console.error(err);
            done({error: err.toString()});
        });
}

WebFont.load({
            google: {
            families: ['Source Sans Pro:400']
            },
    active: load_chart
    })

"""


def enable_altair():
    # do basic config for altair
    # register the custom theme under a chosen name
    alt.themes.register('mysoc_theme', lambda: altair_theme.mysoc_theme)
    # enable the newly registered theme
    alt.themes.enable('mysoc_theme')
    alt.renderers.enable("png")
