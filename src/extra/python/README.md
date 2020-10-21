# Isca: utilities for running Isca experiments and performing data analysis

Please refer to the [main README](../../../README.md) for more info.

Suggested installation procedure:
      $ cd $GFDL_BASE/src/extra/python
      $ pip install -e .
This installs the package in *development mode* i.e. any changes you make to the python files
or any additional files you add will be immediately available.
In a new python console, from any directory, you can now access the execlim code:
      >>> from isca import experiment
      >>> exp = experiment.Experiment()
      ...
