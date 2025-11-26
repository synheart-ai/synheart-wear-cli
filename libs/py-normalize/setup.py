"""Setup configuration for synheart-normalize."""

from setuptools import setup, find_packages

setup(
    name="synheart-normalize",
    version="0.1.0",
    description="Data normalization utilities for wearable vendor data",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        # No external dependencies for now
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
        ],
    },
    author="Synheart",
    license="MIT",
)
