from setuptools import setup, find_packages

setup(
    name='openbioops-lib',
    version='0.1.0',
    packages=find_packages(),
    install_requires=[
        'scanpy>=1.9.0',
        'pandas>=2.0.0',
        'pyarrow>=12.0.0',
        'torch>=2.2.0',
        'anndata>=0.8.0',
        'numpy>=1.24.0',
    ],
)
