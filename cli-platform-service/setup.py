from setuptools import setup, find_namespace_packages

setup(
    name="cli-anything-platform-service",
    version="1.0.0",
    description="Platform Service CLI - 睿峰智链汽车配件供应链平台 CLI 管理工具",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="CLI-Anything Community",
    author_email="community@cli-anything.cc",
    url="https://github.com/HKUDS/CLI-Anything",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    entry_points={
        "console_scripts": [
            "cli-anything-platform-service=cli_anything.platform_service.platform_service_cli:main",
        ],
    },
    package_data={
        "cli_anything.platform_service": ["skills/*.md"],
    },
    install_requires=[
        "click>=8.0",
        "prompt_toolkit>=3.0",
        "requests>=2.25",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0",
            "pytest-cov>=4.0",
            "black>=22.0",
            "flake8>=5.0",
        ],
        "data-clean": [
            "playwright>=1.40",
            "openpyxl>=3.0",
            "pandas>=1.5",
            "xlrd>=2.0",
        ],
    },
    python_requires=">=3.10",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Office/Business",
    ],
    keywords="platform-service cli api auto-parts supply-chain cli-anything",
    license="MIT",
)
