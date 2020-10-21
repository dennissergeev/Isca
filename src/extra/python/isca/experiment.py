# -*- coding: utf-8 -*-
"""Isca experiment."""
from f90nml import Namelist
from jinja2 import Environment, FileSystemLoader
import json
import sh
import shutil
import tarfile

from . import get_env_file, EventEmitter
from .decorators import destructive, useworkdir
from .diagtable import DiagTable
from .exceptions import FailedRunError, InpOutError
from .loghandler import Logger
from .paths import GFDL_BASE, GFDL_DATA, GFDL_WORK, RESOLUTIONS, TEMPLATE_DIR


class Experiment(Logger, EventEmitter):
    """A basic Isca experiment."""

    runfmt = "run{:04d}"
    restartfmt = "res{:04d}.tar.gz"

    def __init__(
        self, name, codebase, safe_mode=False, workbase=GFDL_WORK, database=GFDL_DATA
    ):
        """Initialise Isca experiment."""
        super(Experiment, self).__init__()

        self.env_source = get_env_file()

        self.name = name
        self.codebase = codebase
        self.safe_mode = safe_mode
        self.workbase = workbase

        # set the default locations of working directory,
        # executable directory, restart file storage, and
        # output data directory.
        self.workdir = self.workbase / "experiment" / self.name
        # where an individual run will be performed
        self.rundir = self.workdir / "run"
        # where run data will be moved to upon completion
        self.datadir = database / self.name
        # where restarts will be stored
        self.restartdir = self.datadir / "restarts"
        self.template_dir = TEMPLATE_DIR

        self.templates = Environment(loader=FileSystemLoader(self.template_dir))

        self.diag_table = DiagTable()
        self.field_table_file = (
            self.codebase.srcdir
            / "extra"
            / "model"
            / self.codebase.name
            / "field_table"
        )
        self.inputfiles = []

        self.namelist = Namelist()

    @destructive
    def rm_workdir(self):
        try:
            shutil.rmtree(self.workdir)
        except FileNotFoundError:
            self.log.warning("Tried to remove working directory but it doesnt exist")

    @destructive
    def rm_datadir(self):
        try:
            shutil.rmtree(self.datadir)
        except FileNotFoundError:
            self.log.warning("Tried to remove data directory but it doesnt exist")

    @destructive
    @useworkdir
    def clear_workdir(self):
        self.rm_workdir()
        self.workdir.mkdir(parents=True)
        self.log.info("Emptied working directory {}".format(self.workdir))

    @destructive
    @useworkdir
    def clear_rundir(self):
        try:
            shutil.rmtree(self.rundir)
        except FileNotFoundError:
            self.log.warning("Tried to remove run directory but it doesnt exist")
        self.rundir.mkdir(parents=True)
        self.log.info("Emptied run directory {}".format(self.rundir))

    def get_restart_file(self, idx):
        return self.restartdir / self.restartfmt.format(idx)

    def get_outputdir(self, run):
        return self.datadir / self.runfmt.format(run)

    def get_default_resolutions(self):
        """Load resolutions from JSON file."""
        with RESOLUTIONS.open("r") as fh:
            self.resolutions = json.load(fh)

    def set_resolution(self, res, num_levels=None):
        """
        Set the resolution of the model, based on the triangular truncations of the spectral core.

        Examples
        --------
        Create a spectral core with enough modes to correspond to a 256x128 lon-lat resolution.
        >>> exp.set_resolution('T85', 25)

        """
        delta = self.resolutions[res]
        if num_levels is not None:
            delta["num_levels"] = num_levels
        self.update_namelist({"spectral_dynamics_nml": delta})

    def update_namelist(self, new_vals):
        """Update the namelist sections, overwriting existing values."""
        for sec in new_vals:
            if sec not in self.namelist:
                self.namelist[sec] = {}
            nml = self.namelist[sec]
            nml.update(new_vals[sec])

    def write_namelist(self, outdir):
        namelist_file = outdir / "input.nml"
        self.log.info("Writing namelist to {}".format(namelist_file))
        # A fixed column width is added to be a fixed number as most string namelist variables are
        # width 256 in Isca, so that width plus some indentation and the namelist parameters own
        # name should not exceed 350 characters. Default f90nml value is 72, which is regularly
        # too short for some namelist variables where directories are pointed to.
        self.namelist.column_width = 350
        self.namelist.write(namelist_file)

    def write_diag_table(self, outdir):
        outfile = outdir / "diag_table"
        self.log.info("Writing diag_table to {}".format(outfile))
        if self.diag_table.is_valid():
            if self.diag_table.calendar is None:
                # diagnose the calendar from the namelist
                cal = self.get_calendar()
                self.diag_table.calendar = cal
            self.diag_table.write(outfile)
        else:
            msg = "No output files defined in the DiagTable. Stopping."
            self.log.error(msg)
            raise InpOutError(msg)

    def write_field_table(self, outdir):
        _field_table = outdir / "field_table"
        self.log.info("Writing field_table to {}".format(_field_table))
        shutil.copy(self.field_table_file, _field_table)

    def log_output(self, outputstring):
        line = outputstring.strip()
        if "warning" in line.lower():
            self.log.warn(line)
        else:
            self.log.debug(line)

    def delete_restart(self, run):
        resfile = self.get_restart_file(run)
        if resfile.is_file():
            resfile.unlink()
            self.log.info("Deleted restart file {}".format(resfile))

    def get_calendar(self):
        """Get the value of 'main_nml/calendar.
        Returns a string name of calendar, or None if not set in namelist.'"""
        if "main_nml" in self.namelist:
            return self.namelist["main_nml"].get("calendar")
        else:
            return None

    def check_for_existing_output(self, i):
        outdir = self.datadir / self.runfmt.format(i)
        return outdir.is_dir()

    @destructive
    @useworkdir
    def run(
        self,
        i,
        restart_file=None,
        use_restart=True,
        multi_node=False,
        num_cores=8,
        overwrite_data=False,
        save_run=False,
        run_idb=False,
        nice_score=0,
        mpirun_opts="",
    ):
        """
        Run the Isca model.

        Parameters
        ----------
        num_cores: integer, optional
            Number of mpi cores to distribute over.
        restart_file: pathlib.Path, optional
            A path to a valid restart archive.
            If None and `use_restart=True`, restart file (i-1) will be used.
        save_run: bool, optional
            If True, copy the entire working directory over to $GFDL_DATA
            so that the run can rerun without the python script. (This uses a lot of disk space!)
        """
        # TODO: finish the docstring

        self.clear_rundir()

        indir = self.rundir / "INPUT"
        outdir = self.get_outputdir(i)
        resdir = self.rundir / "RESTART"

        if self.check_for_existing_output(i):
            if overwrite_data:
                self.log.warning(
                    "Data for run {} exists and `overwrite_data=True`. Overwriting.".format(
                        i
                    )
                )
                shutil.rmtree(outdir)
            else:
                self.log.warn(
                    "Data for run {} exists but `overwrite_data=False`. Stopping.".format(
                        i
                    )
                )
                return

        # Make the output run folders
        for _dir in [indir, resdir, self.restartdir]:  # XXX: what about `resdir`?
            _dir.mkdir()

        self.codebase.write_source_control_status(self.rundir / "git_hash_used.txt")
        self.write_namelist(self.rundir)
        self.write_field_table(self.rundir)
        self.write_diag_table(self.rundir)

        # Copy over the input files
        for filename in self.inputfiles:  # XXX: isn't it empty?
            shutil.copy(filename, indir / filename.name)

        if multi_node:
            mpirun_opts += " -bootstrap pbsdsh -f $PBS_NODEFILE"

        if use_restart and not restart_file and i == 1:
            # no restart file specified, but we are at first run number
            msg = (
                "use_restart=True, but restart_file not specified."
                " As this is run 1, assuming spin-up from namelist"
                "stated initial conditions so continuing."
            )
            self.log.warn(msg)
            use_restart = False

        if use_restart:
            if not restart_file:
                # get the restart from previous iteration
                restart_file = self.get_restart_file(i - 1)
            if not restart_file.is_file():
                msg = "Restart file not found, expecting file {}".format(restart_file)
                self.log.error(msg)
                raise InpOutError(msg)
            else:
                self.log.info("Using restart file {}".format(restart_file))

            self.extract_restart_archive(restart_file, indir)
        else:
            self.log.info("Running without restart file")
            restart_file = None

        vars = {
            "rundir": self.rundir,
            "execdir": self.codebase.builddir,
            "executable": self.codebase.executable_name,
            "env_source": self.env_source,
            "mpirun_opts": mpirun_opts,
            "num_cores": num_cores,
            "run_idb": run_idb,
            "nice_score": nice_score,
        }

        runscript = self.templates.get_template("run.sh")

        # employ the template to create a runscript
        runscript.stream(**vars).dump(self.rundir / "run.sh")

        def _outhandler(line):
            handled = self.emit("run:output", self, line)
            if not handled:  # only log the output when no event handler is used
                self.log_output(line)

        self.emit("run:ready", self, i)
        self.log.info("Beginning run %d" % i)
        try:
            proc = sh.bash(
                str(self.rundir / "run.sh"),
                _bg=True,
                _out=_outhandler,
                _err_to_out=True,
            )
            self.log.info("process running as {}".format(proc.process.pid))
            proc.wait()
        except KeyboardInterrupt as e:
            self.log.error("Manual interrupt, killing process.")
            proc.process.terminate()
            proc.wait()
            raise e
        except sh.ErrorReturnCode as e:
            self.log.error("sh error: {}".format(e))
            msg = "Run {} failed. See log for details.".format(i)
            self.log.error(msg)
            self.emit("run:failed", self)
            raise FailedRunError(msg)

        self.emit("run:complete", self, i)
        self.log.info("Run {} complete".format(i))
        outdir.mkdir()

        if num_cores > 1:
            # use postprocessing tool to combine the output from several cores
            codebase_combine_script = self.codebase.builddir / "mppnccombine_run.sh"
            if not codebase_combine_script.is_file():
                self.log.warning(
                    "Combine script does not exist in the commit you are running Isca from."
                    "Falling back to using $GFDL_BASE/mppnccombine_run.sh script"
                )
                sh.ln(
                    "-s",
                    str(GFDL_BASE / "postprocessing" / "mppnccombine_run.sh"),
                    codebase_combine_script,
                )  # TODO: replace with subprocess or shutil
            combinetool = sh.Command(
                codebase_combine_script
            )  # TODO: replace with subprocess
            for file in self.diag_table.files:
                netcdf_file = "{}.nc".format(file)
                filebase = self.rundir / netcdf_file
                combinetool(self.codebase.builddir, filebase)
                # copy the combined netcdf file into the data archive directory
                shutil.copy(filebase, outdir / netcdf_file)
                # remove all netcdf fragments from the run directory
                for frag in filebase.glob("*"):
                    frag.unlink()
                self.log.debug(
                    "{} combined and copied to data directory".format(netcdf_file)
                )

            for restart in resdir.glob("*.res.nc.0000"):
                restartfile = restart.with_suffix("")
                combinetool(self.codebase.builddir, restartfile)
                # sh.rm(glob.glob(restartfile + ".????"))
                for file in restartfile.parent.glob("*.res.nc.????"):
                    file.unlink()  # TODO: check this!
                self.log.debug("Restart file {} combined".format(restartfile))

            self.emit("run:combined", self, i)
        else:
            for file in self.diag_table.files:
                netcdf_file = "{}.nc".format(file)
                filebase = self.rundir / netcdf_file
                shutil.copy(filebase, outdir / netcdf_file)
                for frag in filebase.glob("*"):
                    frag.unlink()
                self.log.debug("{} copied to data directory".format(netcdf_file))

        # make the restart archive and delete the restart files
        self.make_restart_archive(self.get_restart_file(i), resdir)
        shutil.rmtree(resdir)

        if save_run:
            # copy the complete run directory to GFDL_DATA so that the run can
            # be recreated without the python script if required
            resdir.mkdir(exist_ok=True)
            # sh.cp(["-a", self.rundir, outdir])
            shutil.copy(self.rundir, outdir)
        else:
            # just save some useful diagnostic information
            self.write_namelist(outdir)
            self.write_field_table(outdir)
            self.write_diag_table(outdir)
            self.codebase.write_source_control_status(outdir / "git_hash_used.txt")

        self.clear_rundir()
        self.emit("run:finished", self, i)
        return True

    def make_restart_archive(self, archive_file, restart_directory):
        with tarfile.open(archive_file, "w:gz") as tar:
            tar.add(restart_directory, arcname=".")
        self.log.info("Restart archive created at {}".format(archive_file))

    def extract_restart_archive(self, archive_file, input_directory):
        with tarfile.open(archive_file, "r:gz") as tar:
            tar.extractall(path=input_directory)
        self.log.info(
            "Restart {} extracted to {}".format(archive_file, input_directory)
        )

    def derive(self, new_experiment_name):
        """Derive a new experiment based on this one."""
        new_exp = Experiment(new_experiment_name, self.codebase)
        new_exp.namelist = self.namelist.copy()
        new_exp.diag_table = self.diag_table.copy()
        new_exp.inputfiles = self.inputfiles[:]
        return new_exp

    # TODO: replace this with util functionality
    # def run_parameter_sweep(self, parameter_values, runs=10, num_cores=16):
    #     # parameter_values should be a namelist fragment, with multiple values
    #     # for each study e.g. to vary obliquity:
    #     # exp.run_parameter_sweep({'astronomy_nml': {'obliq': [0.0, 5.0, 10.0, 15.0]}})
    #     # will run 4 independent studies and create data e.g.
    #     # <exp_name>/astronomy_nml_obliq_<0.0, 5.0 ...>/run[1-10]/daily.nc
    #     params = [(sec, name, values) for sec, parameters in parameter_values.items()
    #                     for name, values in parameters.items()]
    #     # make a list of lists of namelist section, parameter names and values
    #     params = [[(a,b,val) for val in values] for a,b,values in params]
    #     parameter_space = itertools.product(params)
    #     for combo in parameter_space:
    #         title = '_'.join(['%s_%s_%r' % (sec[:3], name[:5], val) for sec, name, val in combo])
    #         exp = self.derive(self.name + '_' + title)
    #         for sec, name, val in combo:
    #             exp.namelist[sec][name] = val
    #         exp.clear_rundir()
    #         exp.run(1, use_restart=False, num_cores=num_cores)
    #         for i in range(runs-1):
    #             exp.run(i+2)


# class RunSpec(Logger):
#     def __init__(self, exp):
#         self.exp = exp
