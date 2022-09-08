import nbformat
from nbconvert.preprocessors import ExecutePreprocessor
from pathlib import Path


def run_notebook(notebook_filename: Path):
    """
    Run a notebook as part of another process
    """
    print("Running notebook: ", notebook_filename)
    with open(notebook_filename) as f:
        nb = nbformat.read(f, as_version=4)
        ep = ExecutePreprocessor(timeout=600)
        ep.preprocess(nb, {"metadata": {"path": "notebooks/"}})
    with open(notebook_filename, "w", encoding="utf-8") as f:
        nbformat.write(nb, f)
    print("Done")
