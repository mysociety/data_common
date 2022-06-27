# mySociety standard data repository

This is a pattern for running mySociety Jupyter notebooks. See `notebooks\example.ipynb` for an example of use.

# Structure of this repo

- `.devcontainer` - The setup instructions for vscode and codespaces to work with the relevant dockerfile. Includes expected exemptions.
- `.vscode` - Default code processing settings for vscode.
- `data` - data storage. Has some subfolders to help with common sorting. Files put in `data\private` will not be committed.
- `docs` - jekyll directory that maps to the github pages site for this repo.
- `notebooks` - store any jupyter notebooks here. 
- `script` - script-to`rule`them`all directory.
- `src/data_common` - submodule for the `data_common` repo that contains common tools and helper libraries. This also contains the
- `src/[repo_name]` - where you should put specific python scripts for this repository. 
- `tests` - directory for pytest tests. 
- `Dockerfile.dev` - The dockerfile for this repo. Is locked to the `data_common` image at the latest commit when the repo was upgraded. This can be updated if you make changes that require a new docker setup. 

# Code standards

This repo uses:

- black formatting for python
- pyright's 'basic' type checking for python

`script/test`, as well as running all pytests, enforces black formatting over the repository and pyright's 'basic' checking for python typing. This should in many cases be undemanding (and ignore absent coding), but can be disabled by removing it from the `script/test` file.

## Dataset management

This repo template is meant to help manage and publish datasets in a light-weight way. 

A csv table + accompanying resource and schema is a frictionless 'resource'.  Multiple 'resources' can be joined in a frictionless data package.

A published data package will use Jekyll and GitHub pages to render help and download links for different versions. 

### Helper tool

The `dataset` helper tool uses the [frictionless standard](https://specs.frictionlessdata.io/data-package/) to describe datasets. 

A description of all functions can be seen with `dataset --help`.

If there is only one package, you do not need to specify which package you are referring to.

If you have multiple packages, you can:
 - Use '--all` to do the action to all files.
 - Use `--slug [package_slug]` to select a specific action.
 - Run `dataset` from a terminal where the working directory is the package to select that package.

### Package structure

Packages are stored in `data\packages`. Each subfolder is a separate package.
The file structure will be something like.

- versions/ - A folder that contains previously published versions of the files.
- datapackage.yaml - the main configuration file for the datapackage.
- file.csv - a file that contains data (a 'resource').
- file.resource.yaml - a file that contains the metadata description of the resoruce and its contents. 

### Managing a new dataset

- Run `dataset create` - this will walk you through a series of questions and create a config file in `data\packages\[dataset_name]`.
- Either manually or using scripts in `src\[repo]` create csv files inside this folder.
    - If using a script to update the data, you can update the 'custom.build' parameter in the datapackage.yaml to specify how the data should be rebuilt.
    - This can either be a shell command, or a link to python function e.g. `package_name.module:function_name`.
    - `dataset build` will then run this function and update the schema if needed. 
- Then run 'dataset update-schema'. This will create a yaml file for each csv with the schema of the csv file. If this file already exists, it will add any new columns, while preserving previous manual descriptions. 
- Your task is then, through all `*.resource.yaml` files in the directory, to go through and fill in the `description` field (and title where missing). 
- `dataset detail` will tell you which fields remain to be filled in. When you think you've got them all, `dataset validate` will tell you if you've created a valid data package that passes tests.
- `dataset version initial -m "Initial version"` will configure this as the first release (0.1.0)

### Adding tests to the data

A new package `datapackage.yaml` file will contain a `custom.tests` lists, which refer to pytest files in the `tests/` directory. If a file is absent, this does not throw an error. If a file does exist, it will run the tests as part of validation. 

### Versioning and publishing

Publishing data and data updates has two steps. Data is 'versioned' and then 'published'. 

#### Versioning

The dataset tool stores and releases different versions to allow data to be updated while not breaking external references to data. 

This follows the semver standard where there is a major, minor, and patch component.

e.g. Version 1.1.2 - Major(1), Minor(1.1), Patch(1.1.2).

In the public display, the current latest version for a major (v1) or minor (v1.1) or just the latest overall ('latest') can be referenced. These can be used to set some safety in how a file is referenced by another script. For instance, locking to the current major version should isolate a downstream script from backwards incompatible changes until the reference can be tested and updated. 

Generally, the rules for when you should update [follow the frictionless guide](https://specs.frictionlessdata.io/patterns/#specification-7), with some small modifications.

MAJOR version when you make incompatible changes, e.g.

* Change the data package, resource or field name or identifier
* Remove or re-order fields
* Add a field not at the end of a table.
* Change a field type or format
* Change the licence.

MINOR version when you add data or change metadata in a backwards-compatible manner, e.g.

* Add a new data resource to a data package
* Add a new field to the end of a table.
* Add new data to an existing data resource

PATCH version when you make backwards-compatible fixes, e.g.

* Correct errors in existing data
* Change descriptive metadata properties

This follows the general pattern than things before the first major release are unstable, and all major changes can be designated as minor changes. 

This can be updated using a similar syntax to the poetry version tool.

`dataset version minor -m "Added a new column"` - will bump to the next minor version with the associated comment. 

The dataset tool can automatically detect changes and suggest the appropriate bump.

`dataset version auto --dry-run` - will examine the difference between the current and previous version and determine an appropriate bump rule and message. Omit `--dry-run` to update for real.

For automated processes, it can be useful to not allow it to increment a major version.  `dataset version auto --auto-ban major` will cause an error to be raised if a major change is detected. 

#### Publish

The publishing process builds from the versioned datapackage and assembles the jekyll help pages and composite files (excel, json, sqlite) for the overall datapacakge. 

This can be run with `dataset publish`. 

To run a preview server, use `script\server`.

### Extra notes

- If you want resources to be in a specific order on the website or the Excel sheet, you can use the `sheet_order` property in the resource YAML. This expects a number and the default is 999. Otherwise, files are ordered alphabetically. 
- If you add/remove columns from a table or change the value types, the validation will start to fail. `dataset refresh` will update with new column information, but preserve previous descriptions added (but no other manual changes). 

## How to use notebooks

In a new notebook, add the boilerplate:

```
from data_common.notebook import *
```

This will load common libaries like Pandas, Altair, and numpy, as well as the mySociety customisation of these.

# Binder

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

# Uploading

The only build-in uploading steps are to google drive. This needs some additional settings added to the `.env` (see the passwords page on the wiki). Once present, the upload can be run once, and it will trigger the auth workflow to give you the final client key to add to the `.env`.

Once this is done, the render path is defined in the `render.yaml`, where you need to specify both the drive_id and the folder_id (look at the URL of the folder in question). The document will be named with the title defined in `render.yaml`. Caution: google drive allows multiple files of the same name in the same folder, so use the jinja templating to make sure the name changes if the process will be rerun. 

The resulting file can be uploaded with `python manage.py upload`. 

# Parameterised notebooks

If option: rerun is set to true in the `render.yaml`, [papermill](https://github.com/nteract/papermill) is used to add parameters dynamically to notebooks before rendering. 

The way this works is in each notebook, after a code cell that contains `#default-params`, a new cell will be injected containing new parameters. These parameters will be the ones defined in `render.yaml` but can also be overridden in the CLI. For instanceL

`
python manage.py render -p parameter_name parameter_value
`

Will recreate in the injected cell:
`
parameter_name="parameter_value"
`

# Settings and secrets

Once `from data_common import *` is run, a `settings` dict is avaliable. 

This contains variables defined in a top-level `settings.yaml`. [out of date]

Secrets are given a valuein the file as `$$ENV$$` to indicate an enviromental variable of the same name should be used as the source. 

This will also try and extract directly from a top-level `.env` file so the container doesn't have to be reloaded locally to add a new secret.