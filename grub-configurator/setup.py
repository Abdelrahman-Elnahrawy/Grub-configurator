from setuptools import setup, find_packages

setup(
    name="grub-configurator",
    version="1.0.0",
    description="A cross-distro PyQt6 GUI for managing GRUB2 themes, backgrounds, fonts, and Plymouth splash screens",
    author="Your Name",
    python_requires=">=3.10",
    packages=find_packages(),
    install_requires=[
        "PyQt6>=6.4",
    ],
    entry_points={
        "console_scripts": [
            "grub-configurator=grub_configurator.gui:run",
        ],
        "gui_scripts": [
            "grub-configurator-gui=grub_configurator.gui:run",
        ],
    },
)
