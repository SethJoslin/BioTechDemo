CREATE OR REPLACE FILE FORMAT PARQUET_FORMAT TYPE = 'PARQUET';
CREATE OR REPLACE STAGE s3_stage
  URL='s3://your-bucket/openbioops/features/'
  CREDENTIALS=(AWS_KEY_ID='${aws_key}' AWS_SECRET_KEY='${aws_secret}')
  FILE_FORMAT = PARQUET_FORMAT;

COPY INTO FEATURES (sample_id, cell_id, gene_counts, embedding)
FROM @s3_stage FILES = ('features.parquet')
FILE_FORMAT = (FORMAT_NAME = 'PARQUET_FORMAT');