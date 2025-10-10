import argparse
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, lit
from pyspark.sql.types import ArrayType, MapType, StringType


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--brand', required=True)
    parser.add_argument('--raw-path', required=True)
    parser.add_argument('--processed-path', required=True)
    parser.add_argument('--job-date', required=False)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    spark = SparkSession.builder.getOrCreate()

    job_date = args.job_date
    input_path = args.raw_path if not job_date else f"{args.raw_path}/date={job_date}"

    orders_df = spark.read.json(input_path)

    detail_col = col('detail')
    if 'data' in orders_df.columns:
        detail_col = col('data')

    flattened = orders_df.select(
        col('event_type').alias('event_type'),
        col('event_time').alias('event_time'),
        detail_col.alias('order')
    )

    orders = flattened.select('event_type', 'event_time', 'order.*')

    def stringify_complex(column_name: str):
        return col(column_name).cast(StringType()).alias(column_name)

    complex_columns = [f.name for f in orders.schema.fields if isinstance(f.dataType, (ArrayType, MapType))]
    select_cols = [col(c) for c in orders.columns if c not in complex_columns]
    select_cols.extend(stringify_complex(c) for c in complex_columns)

    final_df = orders.select(*select_cols)
    final_df = final_df.withColumn('brand', lit(args.brand))

    final_df.coalesce(1).write.mode('overwrite').parquet(args.processed_path)


if __name__ == '__main__':
    main()
