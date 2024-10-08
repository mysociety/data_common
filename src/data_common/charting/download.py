import json
from typing import List
from urllib.request import urlopen

import altair as alt

from .chart import Chart, LayerChart


def get_chart_spec_from_url(url: str) -> List[str]:
    """
    For extracting chart specs produced by the research sites framework
    """
    response = urlopen(url)
    content = response.read().decode().split("\n")
    content = [x[18:-1] for x in content if "_spec = " in x]
    return content


def json_to_chart(json_spec: str) -> alt.Chart:
    """
    take a json spec and produce a chart
    mostly needed for the weird work arounds needed for importing layer charts
    """
    di = json.loads(json_spec)
    if "layer" in di:
        layers = di["layer"]
        del di["layer"]
        del di["width"]
        chart = LayerChart.from_dict(
            {"config": di["config"], "layer": [], "datasets": di["datasets"]}
        )
        for n, layer in enumerate(layers):
            di_copy = di.copy()
            di_copy.update(layer)
            del di_copy["config"]
            del di_copy["$schema"]
            del di_copy["datasets"]
            del di_copy["width"]
            c = Chart.from_dict(di_copy)
            chart += c  # type: ignore
    else:
        del di["width"]
        del di["config"]["view"]
        chart = Chart.from_dict(di)
    return chart  # type: ignore


def get_chart_from_url(url: str, n: int = 0) -> alt.Chart:
    """
    given url, a number (0 indexed), get the spec,
    and reduce an altair chart instance.
    if `include_df` will try and reduce the original df as well.
    """
    spec = get_chart_spec_from_url(url)[n]
    return json_to_chart(spec)
