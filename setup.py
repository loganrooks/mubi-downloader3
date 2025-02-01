from setuptools import setup, find_packages

setup(
    name="mubi-downloader",
    version="0.1.0",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.8",
    install_requires=[
        "beautifulsoup4>=4.12.0",
        "requests>=2.31.0",
        "browser-cookie3>=0.19.1",
        "python-dotenv>=1.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-mock>=3.11.1",
            "pytest-cov>=4.1.0",
            "coverage>=7.3.0",
        ],
    },
)