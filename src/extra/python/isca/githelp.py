# -*- coding: utf-8 -*-
"""Isca helper functions."""
import sh


git = sh.git.bake("--no-pager")


def url_to_folder(url):
    """Convert a url to a valid folder name."""
    for sym in "/:@":
        url = url.replace(sym, "_")
    return url


def get_git_commit_id(directory):
    try:
        git_dir = directory / ".git"
        commit_id = git(
            "--git-dir=" + str(git_dir), "log", "--pretty=format:'%H'", "-n 1"
        )
        commit_id = str(commit_id).split("'")[1]
    except Exception:  # TODO: use specific exception
        commit_id = None
    return commit_id


def git_diff(directory):
    git_diff_output = sh.git("-C", directory, "diff", "--no-color", ".")
    git_diff_output = str(git_diff_output).split("\n")
    return git_diff_output


def git_run_in_directory(base_dir, dir_in):
    """
    Function that bakes in git command to run in a specified directory.
    `Try except` is to catch different versions of this command
    in versions of git >1.8 (`git -C`) and older versions for which
    `git -C` is not a recognized command.
    """

    try:
        codedir_git = git.bake("-C", base_dir)
        git_test = codedir_git.log("-1", '--format="%H"').stdout  # noqa
        baked_git_fn = git.bake("-C", dir_in)
    except Exception:  # TODO: use specific exception
        codedir_git = git.bake(
            "--git-dir=" + base_dir + "/.git", "--work-tree=" + base_dir
        )
        git_test = codedir_git.log("-1", '--format="%H"').stdout  # noqa
        baked_git_fn = git.bake(
            "--git-dir=" + dir_in + "/.git", "--work-tree=" + dir_in
        )
    return baked_git_fn
