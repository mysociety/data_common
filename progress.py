from rich.progress import Progress
from typing import Optional, Iterable, Callable
from IPython.display import clear_output
from rich import get_console

console = get_console()

def track_progress(iterable: Iterable,
                   name: Optional[str] = None,
                   total: Optional[int] = None,
                   update_label: bool = False,
                   label_func: Optional[Callable] = lambda x: x,
                   clear: Optional[bool] = True):
    """
    simple tracking loop using rich progress
    """
    if name is None:
        name = ""
    if total is None:
        total = len(iterable)
    console.clear_live()
    with Progress(console=console, transient=clear) as progress:
        task = progress.add_task(name, total=total)
        for i in iterable:
            yield i
            if update_label:
                description = f"{name}: {label_func(i)}"
            else:
                description = name
            progress.update(task, advance=1, description=description)