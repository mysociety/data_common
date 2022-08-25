# mySociety standard data repository

This is a common template for running mySociety data science repositories.

It is optimized to run in Github Codespaces, but will also work locally, either using VS code's devcontainer extension, or just using `docker-compose up` to get into docker container.

To start a new project, create a repo from this template: https://github.com/mysociety/python-data-template/generate. This will bootstrap a cookiecutter version of the template, and turn on GitHub Pages. 

# Installing and running a project

The standard data repository is easiest to set up in Codespaces - where opening a new codespace should initalise the repo correctly using stored docker images. This also makes it easier to setup with common secrets. 

All the config required for that also means it works well locally using VS Code and the [remote containers extention](https://code.visualstudio.com/docs/remote/containers) using docker. On opening the project in VS Code, it should prompt to re-open the folder inside the dev container.

To run a single script from outside the container, `docker compose run [x]` should work well. 

The project (in most cases) can be run without docker at all. If python 3.10 is installed locally, you can [install poetry](https://python-poetry.org/) and provision that way:

```bash
pip install poetry
script/setup
python -m poetry install
python -m poetry shell
# now in virtual environment
```

This approach will not (without more manual work) produce the mySociety branded charts well, as that is dependent a selenium setup in the dockerfile. It can handle the dataset tool though. 

# Setting up automated testing/building of github pages

The `.github/workflow-templates` folder can either be renamed `workflows` or used as the building blocks for new workflows.

This currently contains two templates.

- `test.yml` - Use GitHub Actions to enforce automated tests on the project.
- `build.yml` - Build datasets and create a Github Pages page.

# Structure of this repo

- `.devcontainer` - The setup instructions for VS Code and Codespaces to work with the relevant Dockerfile. Includes expected exemptions.
- `.vscode` - Default code processing settings for VS Code.
- `data` - data storage. Has some subfolders to help with common sorting. Files put in `data\private` will not be committed.
- `docs` - Jekyll directory that maps to the GitHub pages site for this repo.
- `notebooks` - store any Jupyter notebooks here. 
- `script` - script-to`rule`them`all directory.
- `src/data_common` - submodule for the `data_common` repo that contains common tools and helper libraries.
- `src/[repo_name]` - where you should put specific python scripts for this repository. 
- `tests` - directory for pytest tests. 
- `Dockerfile.dev` - The Dockerfile for this repo. Is locked to the `data_common` image at the latest commit when the repo was upgraded. This can be updated if you make changes that require a new docker setup. 

# Code formatting and conventions

This repo uses:

- Poetry for dependency management and CLI configuration. 
- Black formatting for Python,
- Pyright's '[basic](https://github.com/microsoft/pyright/blob/main/docs/configuration.md)' type checking for Python. This does not require typing, but highlights issues when known, so projects benefit from having more typing.
- The primary branch is `main`.

Black and Pyright are enforced by `script/test`. This should in many cases be undemanding, but can be disabled by modifying it from the `script/test` file.

See also the general [mySociety coding standards](https://mysociety.github.io/coding-standards.html). 

# Dataset management

This repo template is meant to help manage and publish datasets in a strict but light-weight way. 

The problem this is solving is automated testing and release of datasets that are dynamically generated from ongoing processes. A repo like this sits between the original data source, adds documentation, and tests, and acts as a gate before downstream processes (or other users) make use of the data. It automates the packaging up of the data to make it more accessible with less ongoing work. 

One repo can contain multiple data packages. A data package can contain multiple 'resources' (tables).

A published data package will use Jekyll and GitHub Pages to render help and download links for different versions. This includes a rendered Excel file containing all resources and metadata associated with a dataset. Access to these through the Jekyll site can include a 'soft' email gate (where users are prompted to share information), and a hard email gate, where users must complete a survey before getting access to the datasets. 

## Helper tool

The `dataset` helper tool uses the [frictionless standard](https://specs.frictionlessdata.io/data-package/) to describe datasets. 

A description of all functions can be seen with `dataset --help`.

If there is only one package, you do not need to specify which package you are referring to.

If you have multiple packages, you can:
 - Use `--all` to do the action to all files.
 - Use `--slug [package_slug]` to select a specific action.
 - Run `dataset [anything]` from a terminal where the working directory is the package to select that package.

## Package structure

Packages are stored in `data\packages`. Each subfolder is a separate package.
The file structure will be something like.

- `versions/` - A folder that contains previously published versions of the files.
- `datapackage.yaml` - the main configuration file for the datapackage.
- `file.csv` - a file that contains data (a 'resource').
- `file.resource.yaml` - a file that contains the metadata description of the resource and its contents. 

## Managing a new dataset

- Run `dataset create` - this will walk you through a series of questions and create a config file in `data\packages\[dataset_name]`.
- Either manually or using scripts in `src\[repo]` create csv files inside this folder.
    - If using a script to update the data, you can update the 'custom.build' parameter in the `dtapackage.yaml` to specify how the data should be rebuilt.
    - This can either be a shell command, or a link to python function e.g. `package_name.module:function_name`.
    - `dataset build` will then run this function and update the schema if needed. 
- Then run `dataset update-schema`. This will create a yaml file for each csv with the schema of the csv file. If this file already exists, it will add any new columns, while preserving previous manual descriptions. 
- Your task is then, through all `*.resource.yaml` files in the directory, to go through and fill in the `description` field (and title where missing). 
- `dataset detail` will tell you which fields remain to be filled in. When you think you've got them all, `dataset validate` will tell you if you've created a valid data package that passes tests.
- `dataset version initial -m "Initial version"` will configure this as the first release (0.1.0)

## Adding tests to the data

A new package `datapackage.yaml` file will contain a `custom.tests` lists, which refer to pytest files in the `tests/` directory. If a file is absent, this does not throw an error. If a file does exist, it will run the tests as part of validation. 

You can put all tests in one file, or split over multiple files by adding to the list.
This can be used to make different datapackages use different tests.

`script/test` will run all tests anyway.

## Versioning and publishing

Publishing data and data updates has two steps. Data is 'versioned' and then 'published'. 

### Versioning

The dataset tool stores and releases different versions to allow data to be updated while not breaking external references to data. 

This follows the [semver](https://semver.org/) standard where there is a major, minor, and patch component.

e.g. Version 1.1.2 - Major(1), Minor(1.1), Patch(1.1.2).

In the public display, the current latest version for a major (1) or minor (1.1) or just the latest overall ('latest') can be referenced. These can be used to set some safety in how a file is referenced by another script. For instance, locking to the current major version should isolate a downstream script from backwards incompatible changes to the schema until the reference can be tested and updated. 

Generally, the rules for when you should update [follow the frictionless guide](https://specs.frictionlessdata.io/patterns/#specification-7), with some small modifications.

MAJOR version when you make incompatible changes, e.g.

* Change the data package, resource or field name or identifier
* Remove or re-order fields
* Add a new field not at the end of a table (changing existing order).
* Change a field type or format
* Change the licence.

MINOR version when you add data or change metadata in a backwards-compatible manner, e.g.

* Add a new data resource to a data package
* Add a new field to the end of a table.
* Add new rows to an existing data resource

PATCH version when you make backwards-compatible fixes, e.g.

* Correct errors in existing data (hash of table changes, but not column names or row information)
* Change descriptive metadata properties

This follows the general pattern that before the first major release nothing is stable, and all major changes before v1 can be designated as minor changes. 

This can be updated using a similar syntax to the poetry version tool.

`dataset version minor -m "Added a new column"` - will bump to the next minor version with the associated comment. 

The dataset tool can also automatically detect changes and suggest the appropriate bump.

`dataset version auto --dry-run` - will examine the difference between the current and previous version and determine an appropriate bump rule and message. Omit `--dry-run` to update for real.

In general, **you should not be doing much versioning yourself**. Instead, you should modify either the build script or source data and let GitHub Actions do the work of versioning publishing the data. This avoids the problem of different version increments in different branches. If incrementing directly, you should be in the `main` branch. If `dataset validate` is happy, it will merge OK.

For automated processes, it can be useful to not allow it to increment a major version.  `dataset version auto --auto-ban major` will cause an error to be raised if a major change is detected. If you actually intend to release a major version, this will then need to be done manually.

The pattern for automated testing is a pair of GitHub Actions:

- On pushes on non-main branches, and pull requests, run the tests, and `dataset version auto --dry-run --auto-ban major`. This validates the updates cause no backwards incompatible changes. 
- On push to the main branch, an action does the same, but without the `--dry-run` and with `--publish`, and a step to commit back to the repo. 

Versions of these are stored in `.github/workflow-templates`.

#### Publish

The publishing process builds from the versioned datapackage and assembles the Jekyll help pages and composite files (excel, json, sqlite) for the overall datapackage. 

This can be run with `dataset publish`, or a `--publish` flag can be added to `dataset version` (only run if a version update is successful).

To run a preview server, use `script\server`.

Again, this should be rarely run manually after initial setup. For dynamic datasets, a GitHub Action can be used to run from `dataset build` on a schedule, followed by version and build commands.

## Extra notes

- If you want resources to be in a specific order on the website or the Excel sheet, you can use the `sheet_order` property in the resource YAML. This expects a number and the default is 999. Otherwise, files are ordered alphabetically. 
- For datapackages, `custom.dataset_order` serves the same purpose for the home page in `datapackage.yaml`.
- If you add/remove columns from a table or change the value types, the validation will start to fail. `dataset refresh` will update with new column information, but preserve previous descriptions added (but no other manual changes). 
- Composite downloads (xlsx, json, sqlite) do not need to contain all resources. In `datapackage.json` you can either set datasets to explicitly include or exclude from the composite. 
- You can turn on auto-complete a bash shell for the `dataset` tool and running `dataset autocomplete` and running the resulting command. Check the click cli help for how to adapt it for other shell options.


## How to use notebooks

In a new notebook, add the boilerplate:

```
from data_common.notebook import *
```

This will load common libraries like Pandas, Altair, and numpy, as well as the mySociety customisation of these. It will also set the current working directory to the root of the project.

### Binder

[Binder](https://mybinder.org/) is a tool for demoing and using jupyter notebooks online. Binder links are automatically generated for the repo using the cookiecutter template. This will only work with repos that do not require secrets (these can not safely be loaded into binder).

# Rendering

Render setings are defined in a top-level `render.yaml`. This indicates how notebooks should be grouped into a single `document`. Parameters, the title and the slug (used to define folder structure) can use jinja templating to define their values dynamically. 

The order this works is:

1. Variables are loaded from the context modules. 
2. These variables are used to populate the parameters. Parameters are populated in order, so once the first is defined, it can be used in future parameters.
3. The title and slug can simiilarly use the defined parameters. 

Multiple documents can be defined in the render.yaml. Each document can be specified with the key when using the management commands. e.g. 

`python manage.py render second-example-doc`

Will render the doc with the key of `second-example-doc`. When there is only one document, the key does not need to be specified. 

# Publishing notebooks

The publication flow for notebooks is managed by files in `notebooks/_render_config`. This can combine multiple notebooks into a single output, [parameterize using papermill](https://papermill.readthedocs.io/en/latest/), and output to several options.

A notebook can be rendered and published using the `notebook` tool. Run `notebook --help` to learn more. 

`notebook render` - runs and combined all notebooks into an markdown and .docx file. If you do not want to include these files in the repo, add `_render/` to `.gitignore`.

`notebook publish` will run all publication flows.

These steps can be comabined  with `notebook render --publish`.

The publish options avalible are `gdrive`, `jekyll`, and `readme`. 

Google drive will (with correct env permissions - see the passwords page on the wiki) upload the rendered document.

The config can look like this:

```
upload:
  gdrive:
    g_drive_name: All staff
    g_folder_name: Climate/Metrics
```

You can also specify `[blah]_id` for both and use the drive/folder ids in google drive. 

The Jekyll upload will take the markdown file and move it to the jekyll folder in `docs`. This will make it avaliable in public in the github pages site. Any extra parameters are added to the front matter for the file.

The readme option will output the final file to `readme.md` in the root of the repo. 
This takes 'start' and 'end' parameters that give anchor text to inject the content between. If not set, will override entire readme.



# Parameterised notebooks

If `option: rerun` is set to true in the `render.yaml`, [papermill](https://github.com/nteract/papermill) is used to add parameters dynamically to notebooks before rendering. 

The way this works is in each notebook, after a code cell that contains `#default-params`, a new cell will be injected containing new parameters. These parameters will be the ones defined in `render.yaml` but can also be overridden in the CLI. For instance:

`
python manage.py render -p parameter_name parameter_value
`

Will recreate in the injected cell:
`
parameter_name="parameter_value"
`

# Settings and secrets for notebooks and scripts

Once `from data_common import *` is run, a `settings` dict is available. 

This contains variables defined in `[notebook.settings]` in the `pyproject.toml`.

Secrets are given a value in the file as `$$ENV$$` to indicate an environmental variable of the same name should be used as the source. 

This will also try and extract directly from a top-level `.env` file, so the container doesn't have to be reloaded locally to add a new secret.