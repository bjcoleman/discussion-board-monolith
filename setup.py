from setuptools import setup

setup(
    name="discussion_board",
    version="0.1.0",
    package_dir={"discussion_board": "src"},
    packages=["discussion_board"],
    python_requires=">=3.12",
    install_requires=[
        "Flask>=3.0.0",
        "mysql-connector-python>=9.0.0",
        "gunicorn>=21.2.0",
        "python-dotenv>=1.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=8.0.0",
            "pytest-cov>=4.1.0",
        ],
    },
)