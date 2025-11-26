"""Setup configuration for synheart-cloud-connector."""

from setuptools import setup, find_packages

setup(
    name="synheart-cloud-connector",
    version="0.1.0",
    description="OAuth token management for Synheart wearable vendor integrations",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "boto3>=1.26.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "moto>=4.0.0",  # For mocking AWS services
        ],
    },
    author="Synheart",
    license="MIT",
)
