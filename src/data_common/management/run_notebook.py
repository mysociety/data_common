from pathlib import Path

import nbformat
from nbconvert.preprocessors.execute import ExecutePreprocessor


def run_notebook(notebook_filename: Path, save: bool = True):
    """
    Run a notebook as part of another process
    """
    print("Running notebook: ", notebook_filename)
    with open(notebook_filename) as f:
        nb = nbformat.read(f, as_version=4)
        ep = ExecutePreprocessor(timeout=600)
        ep.preprocess(nb, {"metadata": {"path": "notebooks/"}})
    if save:
        print(f"Saving notebook: {notebook_filename}")
        with open(notebook_filename, "w", encoding="utf-8") as f:
            nbformat.write(nb, f)
    print("Done")
