from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq
import pandas as pd
import geopandas as gpd
import math
from tqdm import tqdm
from geopandas.io.arrow import _arrow_to_geopandas


def write_split_parquet(
    from_file: Path,
    output_path: Path,
    chunk_size: int = 1000,
    compression: str = "GZIP",
    silent: bool = False,
):
    """
    Split a Parquet file into multiple Parquet files.
    """
    # initialize output directory
    if not output_path.exists():
        output_path.mkdir(parents=True)

    if output_path.exists() and not output_path.is_dir():
        raise ValueError("Output path is not a directory.")

    else:
        for file in output_path.iterdir():
            file.unlink()
    table = pa.parquet.read_table(from_file)

    # Calculate the total number of records
    total_records = table.num_rows

    # Calculate the number of chunks needed
    num_chunks = math.ceil(total_records / chunk_size)

    # Split the table into chunks and write to separate Parquet files
    for chunk_idx in tqdm(list(range(num_chunks)), disable=silent):
        start_idx = chunk_idx * chunk_size
        end_idx = min((chunk_idx + 1) * chunk_size, total_records)

        # Slice the table to create a new chunk
        chunk_table = table.slice(start_idx, end_idx - start_idx)

        # Write the chunk to a Parquet file
        output_file = output_path / f"{chunk_idx}.parquet"
        pq.write_table(chunk_table, output_file, compression=compression)


def read_parquet_directory_to_table(directory_path: Path) -> pa.Table:
    """
    Read all Parquet files in a directory and combine them into a single PyArrow Table.
    """
    parquet_files = [
        file for file in directory_path.iterdir() if file.suffix == ".parquet"
    ]
    if not parquet_files:
        raise ValueError("No Parquet files found in the directory.")

    # Read Parquet files and combine them into a single DataFrame
    tables = []
    for file in parquet_files:
        table = pq.read_table(file)
        tables.append(table)

    return pa.concat_tables(tables)


def read_parquet_directory(directory_path: Path) -> pd.DataFrame:
    """
    Read all Parquet files in a directory and combine them into a single Pandas DataFrame.
    """
    table = read_parquet_directory_to_table(directory_path)
    return table.to_pandas()


def read_split_geoparquet(fromdir: Path) -> gpd.GeoDataFrame:
    """
    Read all Parquet files in a directory and combine them into a single GeoPandas DataFrame.
    """
    table = read_parquet_directory_to_table(fromdir)
    # convert pyarrow table to geopandas dataframe
    return _arrow_to_geopandas(table)


def open_geo_file(file_path: Path) -> gpd.GeoDataFrame:
    """
    Open a GeoFile (GeoJSON, Shapefile, GeoPackage, etc.) and return a GeoDataFrame.
    """

    # if the file_path is a directory return a GeoDataFrame
    if file_path.is_dir():
        return read_split_geoparquet(file_path)
    # if the file_name is "*.parquet", get the parent directory and return a GeoDataFrame
    elif file_path.name == "*.parquet":
        return read_split_geoparquet(file_path.parent)
    # if it's another parquet file, return that using the normal method
    elif file_path.suffix == ".parquet":
        return gpd.read_parquet(file_path)
    # if it's a GeoJSON, Shapefile, GeoPackage, etc. return that using the normal method
    else:
        return gpd.read_file(file_path)
