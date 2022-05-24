import json
import os
import sqlite3
import warnings
from dataclasses import dataclass
from pathlib import Path
from shutil import copyfile
from typing import Any, Literal, TypedDict

import pandas as pd
import rich
import xlsxwriter
from frictionless import Schema, describe, validate
from rich.markdown import Markdown
from rich.table import Table
from ruamel.yaml import YAML

from .jekyll_management import collect_jekyll_data
from .rich_assist import PanelPrint, df_to_table
from .settings import get_settings
from .table_management import SchemaValidator, update_table_schema


class ResourceStub(TypedDict):
    name: str
    title: str
    licence: dict[str, str]


alert_colors = Literal["red"] | Literal["green"] | Literal["orange"] | Literal["blue"]
ValidationErrors = list[tuple[str, alert_colors]]


def make_color(item: str, color: alert_colors) -> str:
    return f"[{color}]{item}[/{color}]"


def color_print(item: str, color: alert_colors, new_line: bool = True) -> None:
    rich.print(make_color(item, color), end="\n" if new_line else " ")


@dataclass
class DataResource:
    path: Path

    @property
    def slug(self) -> str:
        return self.path.stem

    def get_order(self) -> int:
        """
        Get a sheet order if one has been set
        """
        desc = self.get_resource()
        return desc.get("sheet_order", 999)

    @property
    def resource_path(self) -> Path:
        """
        Path to a yaml file describing this resource
        """
        return self.path.parent / (self.slug + ".resource.yaml")

    @property
    def has_resource_yaml(self) -> bool:
        return self.resource_path.exists()

    def validate_descriptions(self) -> str:
        """
        Enforce checks on optional title and description parameters
        """
        if self.has_resource_yaml is False:
            return "Missing schema"

        problems: list[tuple[str, str]] = []

        desc = self.get_resource()
        if not desc["title"]:
            problems.append(("title", "resource"))
        if not desc["description"]:
            problems.append(("description", "resource"))

        for f in desc["schema"]["fields"]:
            if not f["description"]:
                problems.append(("description", f["name"]))

        if len(problems) == 0:
            return ""
        else:
            problems_str = [" for ".join(x) for x in problems]
            return "Missing: " + ", ".join(problems_str)

    def get_status(self) -> tuple[str, alert_colors]:
        """
        Check for errors in a resource
        """
        if not self.has_resource_yaml:
            return "No resource file", "red"
        if desc_error := self.validate_descriptions():
            return desc_error, "red"
        valid_check = validate(self.resource_path)
        if valid_check["stats"]["errors"] > 0:
            return valid_check["tasks"][0]["errors"], "red"
        return "Valid resource", "green"

    def get_resource(self) -> dict[str, Any]:
        if self.has_resource_yaml:
            yaml = YAML(typ="safe")
            with open(self.resource_path, "r") as f:
                if resource := yaml.load(f):
                    return resource
        return {}

    def get_metadata_df(self) -> pd.DataFrame:
        if self.has_resource_yaml is False:
            raise ValueError("Trying to get metadata for {self.slug}, but not present.")
        resource = self.get_resource()
        df = pd.DataFrame(resource["schema"]["fields"])
        df["unique"] = df["constraints"].apply(
            lambda x: "Yes" if x.get("unique", False) else "No"
        )
        df["options"] = df["constraints"].apply(lambda x: ", ".join(x.get("enum", [])))
        df = df.drop(columns=["constraints"]).rename(columns={"name": "column"})
        df = df[["column", "description", "type", "example", "unique", "options"]]
        return df

    def get_schema_from_file(
        self, existing_schema: SchemaValidator | None
    ) -> SchemaValidator:
        return update_table_schema(self.path, existing_schema)

    def rebuild_yaml(self):
        """
        Recreate yaml file from bananas
        """
        from frictionless.resource.resource import Resource

        existing_desc = self.get_resource()
        desc = describe(self.path)
        desc.update(existing_desc)

        desc["schema"] = self.get_schema_from_file(existing_desc.get("schema", None))
        desc["path"] = self.path.name

        new_dict = {"title": None, "description": None}

        new_dict.update(desc.to_dict())

        yaml = YAML()
        yaml.default_flow_style = False
        with open(self.resource_path, "w") as f:
            yaml.dump(new_dict, f)
        print(f"Updated config for {self.slug} to {self.resource_path}")


@dataclass
class DataPackage:
    path: Path

    @property
    def slug(self) -> str:
        return self.path.stem

    @property
    def datapackage_path(self) -> Path:
        return self.path / "datapackage.yaml"

    def build_path(self) -> Path:
        build_path = get_settings()["publish_dir"] / "data" / self.slug
        if build_path.exists() is False:
            build_path.mkdir()
        return build_path

    def __post_init__(self):
        if self.datapackage_path.exists() is False:
            raise ValueError(f"No datapackage.yaml found in {self.path}")

    def resources(self) -> dict[str, DataResource]:

        resources = [DataResource(path=x) for x in self.path.glob("*.csv")]
        resources.sort(key=lambda x: x.slug)
        resources.sort(key=lambda x: x.get_order())
        return {x.slug: x for x in resources}

    @property
    def resource_count(self) -> int:
        return len(self.resources())

    @property
    def url(self) -> str:
        return get_settings()["publish_url"] + self.slug + "/"

    def rebuild_resource(self, slug: str):
        resource = self.resources()[slug]
        resource.rebuild_yaml()

    def rebuild_all_resources(self):
        for resource in self.resources().values():
            resource.rebuild_yaml()

    def get_datapackage(self) -> dict[str, Any]:
        yaml = YAML(typ="safe")
        with open(self.datapackage_path, "r"):
            return yaml.load(self.datapackage_path)

    def validate(self) -> ValidationErrors:
        desc = self.get_datapackage()
        validation_errors: ValidationErrors = []
        if not desc.get("description", ""):
            validation_errors.append(("Missing package description", "red"))
        if not desc.get("title", ""):
            validation_errors.append(("Missing package title", "red"))
        if not desc.get("licenses", ""):
            validation_errors.append(("Missing package licence", "red"))
        for r in self.resources().values():
            if r.get_status()[1] == "red":
                validation_errors.append((f"Invalid resource {r.slug}", "red"))
        return validation_errors

    def build_package(self):
        """
        Build package files and move to jekyll directory
        """

        color_print(f"Building package: {self.slug}", "red")
        color_print("Building datapackage.json", "blue", new_line=False)
        self.build_json()
        color_print("✔️", "green")
        color_print("Copying resources", "blue", new_line=False)
        self.copy_resources()
        color_print("✔️", "green")
        color_print("Checking package validity", "blue", new_line=False)
        self.check_build_integrity()
        color_print("✔️", "green")
        color_print("Building composite files", "blue", new_line=False)
        self.build_composites()
        color_print("✔️", "green")
        color_print("Gathering Jekyll information", "blue", new_line=False)
        collect_jekyll_data()
        color_print("✔️", "green")

    def check_build_integrity(self):
        """
        run the validator against the data pacakge
        """

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore")
            valid_results = validate(
                self.build_path() / "datapackage.json", type="package"
            )
        if valid_results["stats"]["errors"] > 0:
            raise ValueError(valid_results)

    def copy_resources(self):
        """
        Copy the CSVs over
        """
        for r in self.resources().values():
            copyfile(r.path, self.build_path() / r.path.name)

    def build_json(self):
        """
        Create full json datapackage file for all resources
        """
        datapackage = self.get_datapackage()
        datapackage["resources"] = [x.get_resource() for x in self.resources().values()]
        with open(self.build_path() / "datapackage.json", "w") as f:
            json.dump(datapackage, f, indent=4)

    def build_coversheet(self, writer: pd.ExcelWriter) -> pd.ExcelWriter:
        desc = self.get_datapackage()
        settings = get_settings()

        bold = writer.book.add_format({"bold": True})

        ws = writer.book.add_worksheet("package_description")
        ws.set_column(2, 2, 40)
        ws.set_column(3, 3, 30)
        ws.write(2, 2, "Dataset", bold)
        ws.write(2, 3, desc["title"])
        ws.write(3, 2, "URL", bold)
        ws.write(3, 3, self.url)
        ws.write(4, 2, "Dataset description", bold)
        ws.write(4, 3, desc["description"])
        if "licenses" in desc:
            ws.write(5, 2, "Licence", bold)
            for n, licence in enumerate(desc["licenses"]):
                ws.write_url(5, 3 + n, licence["path"], string=licence["title"])
        if "version" in desc:
            ws.write(6, 2, "Version", bold)
            ws.write(6, 3, desc["version"])

        row = 8

        if "contributors" in desc:
            ws.write(row, 2, "Contributors", bold)
            row += 1
            for contrib in desc["contributors"]:
                author = contrib.get("title", "")
                org = contrib.get("organization", "")
                if author and org:
                    credit = f"{author} ({org})"
                elif author:
                    credit = author
                else:
                    credit = org
                url = contrib.get("path", "")
                if url:
                    ws.write_url(row, 2, url, string=credit)
                else:
                    ws.write(row, 2, credit)
                row += 1

        if "sources" in desc:
            row += 1
            ws.write(row, 2, "Sources", bold)
            row += 1
            for source in desc["sources"]:
                title = source["title"]
                url = source.get("path", "")
                if url:
                    ws.write_url(row, 2, url, string=title)
                else:
                    ws.write(row, 2, title)
                row += 1

        row += 2
        ws.write(row, 2, "Sheet", bold)
        ws.write(row, 3, "Metadata", bold)
        ws.write(row, 4, "Sheet description", bold)
        row += 1

        # sort sheets in order

        for r in self.resources().values():
            desc = r.get_resource()
            metadata_sheet = f"{r.slug}_metadata"[-31:]
            ws.write_url(row, 2, f"internal:{r.slug}!A1", string=desc["title"])
            ws.write_url(
                row,
                3,
                f"internal:{metadata_sheet}!A1",
                string="View column information",
            )
            ws.write(row, 4, desc["description"])
            row += 1

        row += 1
        ws.write_url(
            row,
            2,
            settings["credit_url"] + f"?dataset_slug={self.slug}",
            string=settings["credit_text"],
        )

        return writer

    def build_excel(self):
        """
        Build a single excel file for all resources
        """
        sheets: dict[str, pd.DataFrame] = {}

        for slug, resource in self.resources().items():
            sheets[slug] = pd.read_csv(resource.path)
            sheets[slug + "_metadata"] = resource.get_metadata_df()

        excel_path = self.build_path() / f"{self.slug}.xlsx"

        writer = pd.ExcelWriter(excel_path)
        writer = self.build_coversheet(writer)

        for sheet_name, df in sheets.items():
            short_sheet_name = sheet_name[-31:]  # only allow 31 characters
            df.to_excel(writer, sheet_name=short_sheet_name, index=False)

            for column in df:
                column_length = max(df[column].astype(str).map(len).max(), len(column))
                column_length += 4
                col_idx = df.columns.get_loc(column)
                writer.sheets[short_sheet_name].set_column(
                    col_idx, col_idx, column_length
                )
        writer.save()

    def build_sqlite(self):

        sheets = {}
        metadata: list[pd.DataFrame] = []

        for slug, resource in self.resources().items():
            sheets[slug] = pd.read_csv(resource.path)
            meta_df = resource.get_metadata_df()
            meta_df["resource"] = slug
            metadata.append(meta_df)

        sheets["data_description"] = pd.concat(metadata)

        sqlite_file = self.build_path() / f"{self.slug}.sqlite"

        if sqlite_file.exists():
            sqlite_file.unlink()
        con = sqlite3.connect(sqlite_file)
        for name, df in sheets.items():
            df.to_sql(name, con, index=False)
        con.close()

    def build_composites(self):
        """
        Create composite files for the datapackage
        """
        self.build_excel()
        self.build_sqlite()

    def build_markdown(self):
        """
        Create composite files for the datapackage
        """
        ...

    def print_status(self):

        resources = list(self.resources().values())

        df = pd.DataFrame(
            {
                "Resource": [x.slug for x in resources],
                "Status": [make_color(*x.get_status()) for x in resources],
            }
        )

        data = self.get_datapackage()

        panel = PanelPrint(
            title=data["name"],
            subtitle="For more options `dataset --help`",
            padding=1,
            expand=False,
            width=200,
        )

        panel.print("")
        panel.print("[u]Data Package[/u]")
        panel.print("")
        panel.print(f"{data['title']}")
        panel.print("")
        panel.print("[u]Description[/u]")
        panel.print("")
        panel.print(data["description"])
        table = Table(header_style="bold blue", expand=False)
        table = df_to_table(df, table, show_index=False)
        panel.print("")
        panel.print("[u]Resource status[/u]")
        panel.print("")
        panel.print(table)
        panel.display()
