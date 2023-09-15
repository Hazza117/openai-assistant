from setuptools import setup, find_packages

setup(
    name='assistant',
    version='0.0.1',
    author='Harrison Blee',
    description='GPT Assistant that can list, write, read, and execute python files',
    packages=find_packages(),
    install_requires=['openai', 'click', 'colorama'],
    entry_points={
        'console_scripts': ['assistant=assistant.cli:assistant'],
    }
)