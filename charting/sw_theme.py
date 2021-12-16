"""
mySociety colours and themes for altair
just needs to be imported before rendering charts
Mirrors ggplot theme
"""

import altair as alt
from typing import List, Any, Optional

# brand colours
colours = {
    "colour_orange": "#f79421",
    "colour_off_white": "#f3f1eb",
    "colour_light_grey": "#e2dfd9",
    "colour_mid_grey": "#959287",
    "colour_dark_grey": "#6c6b68",
    "colour_black": "#333333",
    "colour_red": "#dd4e4d",
    "colour_yellow": "#fff066",
    "colour_violet": "#a94ca6",
    "colour_green": "#61b252",
    "colour_green_dark": "#53a044",
    "colour_green_dark_2": "#388924",
    "colour_blue": "#54b1e4",
    "colour_blue_dark": "#2b8cdb",
    "colour_blue_dark_2": "#207cba",
}

# based on data visualisation colour palette
adjusted_colours = {
    "sw_yellow": "#fed876",
    "sw_berry": "#e02653",
    "sw_blue": "#0ba7d1",
    "sw_dark_blue": "#065a70",
}


monochrome_colours = {
    "colour_blue_light_20": "#7ddef8",
    "colour_blue": "#0ba7d1",
    "colour_blue_dark_20": "#076d88",
    "colour_blue_dark_30": "#033340",
}

all_colours = colours.copy()
all_colours.update(adjusted_colours)
all_colours.update(monochrome_colours)

palette = ["sw_yellow", "sw_berry", "sw_blue", "sw_dark_blue"]


contrast_palette = ["sw_dark_blue", "sw_yellow", "sw_berry", "sw_blue"]


palette = contrast_palette

monochrome_palette = [
    "colour_blue_light_20",
    "colour_blue",
    "colour_blue_dark_20",
    "colour_blue_dark_30",
]

palette_colors = [adjusted_colours[x] for x in palette]

contrast_palette_colors = [adjusted_colours[x] for x in contrast_palette]

monochrome_palette_colors = [monochrome_colours[x] for x in monochrome_palette]


# set default of colours
original_palette = [
    # Start with category10 color cycle:
    "#1f77b4",
    "#ff7f0e",
    "#2ca02c",
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#7f7f7f",
    "#bcbd22",
    "#17becf",
    # Then continue with the paired lighter colors from category20:
    "#aec7e8",
    "#ffbb78",
    "#98df8a",
    "#ff9896",
    "#c5b0d5",
    "#c49c94",
    "#f7b6d2",
    "#c7c7c7",
    "#dbdb8d",
    "#9edae5",
]

# use new palette for as long as possible
sw_palette_colors = palette_colors + original_palette[len(palette_colors) :]


def color_scale(
    domain: List[Any],
    monochrome: bool = False,
    reverse: bool = False,
    palette: Optional[List[Any]] = None,
    named_palette: Optional[List[Any]] = None,
) -> alt.Scale:
    if palette is None:
        if monochrome:
            palette = monochrome_palette_colors
        else:
            palette = sw_palette_colors
    if named_palette is not None:
        if monochrome:
            palette = [monochrome_colours[x] for x in named_palette]
        else:
            palette = [all_colours[x] for x in named_palette]
    use_palette = palette[: len(domain)]
    if reverse:
        use_palette = use_palette[::-1]
    return alt.Scale(domain=domain, range=use_palette)


font = "Lato"

sw_theme = {
    "config": {
        "padding": {"left": 5, "top": 5, "right": 20, "bottom": 5},
        "title": {"font": font, "fontSize": 30, "anchor": "start"},
        "axis": {
            "labelFont": font,
            "labelFontSize": 14,
            "titleFont": font,
            "titleFontSize": 16,
            "offset": 0,
        },
        "axisX": {
            "labelFont": font,
            "labelFontSize": 14,
            "titleFont": font,
            "titleFontSize": 16,
            "domain": True,
            "grid": True,
            "ticks": False,
            "gridWidth": 0.4,
            "labelPadding": 10,
        },
        "axisY": {
            "labelFont": font,
            "labelFontSize": 14,
            "titleFont": font,
            "titleFontSize": 16,
            "titleAlign": "left",
            "labelPadding": 10,
            "domain": True,
            "ticks": False,
            "titleAngle": 0,
            "titleY": -10,
            "titleX": -50,
            "gridWidth": 0.4,
        },
        "view": {
            "stroke": "transparent",
            "continuousWidth": 700,
            "continuousHeight": 400,
        },
        "line": {
            "strokeWidth": 3,
        },
        "bar": {"color": palette_colors[0]},
        "mark": {"shape": "cross"},
        "legend": {
            "orient": "bottom",
            "labelFont": font,
            "labelFontSize": 12,
            "titleFont": font,
            "titleFontSize": 12,
            "title": "",
            "offset": 18,
            "symbolType": "square",
        },
    }
}


sw_theme.setdefault("encoding", {}).setdefault("color", {})["scale"] = {
    "range": sw_palette_colors,
}
