#!/usr/bin/env python3

"""Module containing the Editconf class and the command line interface."""
import os
import argparse
import shutil
from biobb_common.configuration import  settings
from biobb_common.tools import file_utils as fu
from biobb_common.command_wrapper import cmd_wrapper
from biobb_md.gromacs.common import get_gromacs_version
from biobb_md.gromacs.common import GromacsVersionError

class Editconf():
    """Wrapper class for the GROMACS editconf (http://manual.gromacs.org/current/onlinehelp/gmx-editconf.html) module.

    Args:
        input_gro_path (str): Path to the input GRO file.
        output_gro_path (str): Path to the output GRO file.
        properties (dic):
            | - **distance_to_molecule** (*float*) - (1.0) Distance of the box from the outermost atom in nm. ie 1.0nm = 10 Angstroms.
            | - **box_type** (*str*) - ("cubic") Geometrical shape of the solvent box. Available box types: (http://manual.gromacs.org/current/onlinehelp/gmx-editconf.html) -bt option.
            | - **center_molecule** (*bool*) - (True) Center molecule in the box.
            | - **gmx_path** (*str*) - ("gmx") Path to the GROMACS executable binary.
            | - **remove_tmp** (*bool*) - (True) [WF property] Remove temporal files.
            | - **restart** (*bool*) - (False) [WF property] Do not execute if output files exist.
    """

    def __init__(self, input_gro_path, output_gro_path, properties=None, **kwargs):
        properties = properties or {}

        # Input/Output files
        self.input_gro_path = input_gro_path
        self.output_gro_path = output_gro_path

        # Properties specific for BB
        self.distance_to_molecule = properties.get('distance_to_molecule', 1.0)
        self.box_type = properties.get('box_type', 'cubic')
        self.center_molecule = properties.get('center_molecule', True)

        # Properties common in all GROMACS BB
        self.gmxlib = properties.get('gmxlib', None)
        self.gmx_path = properties.get('gmx_path', 'gmx')
        self.gmx_nobackup = properties.get('gmx_nobackup', True)
        self.gmx_nocopyright = properties.get('gmx_nocopyright', True)
        if self.gmx_nobackup:
            self.gmx_path += ' -nobackup'
        if self.gmx_nocopyright:
            self.gmx_path += ' -nocopyright'
        if not properties.get('docker_path'):
            self.gmx_version = get_gromacs_version(self.gmx_path)

        # Properties common in all BB
        self.can_write_console_log = properties.get('can_write_console_log', True)
        self.global_log = properties.get('global_log', None)
        self.prefix = properties.get('prefix', None)
        self.step = properties.get('step', None)
        self.path = properties.get('path', '')
        self.remove_tmp = properties.get('remove_tmp', True)
        self.restart = properties.get('restart', False)

        # Docker Specific
        self.docker_path = properties.get('docker_path')
        self.docker_image = properties.get('docker_image', 'mmbirb/pmx')
        self.docker_volume_path = properties.get('docker_volume_path', '/inout')

        # Check the properties
        fu.check_properties(self, properties)

    def launch(self):
        """Launches the execution of the GROMACS editconf module."""
        tmp_files = []

        #Create local logs
        out_log, err_log = fu.get_logs(path=self.path, prefix=self.prefix, step=self.step, can_write_console=self.can_write_console_log)

        #Check GROMACS version
        if not self.docker_path:
            if self.gmx_version < 512:
                raise GromacsVersionError("Gromacs version should be 5.1.2 or newer %d detected" % self.gmx_version)
            fu.log("GROMACS %s %d version detected" % (self.__class__.__name__, self.gmx_version), out_log)

        #Restart if needed
        if self.restart:
            output_file_list = [self.output_gro_path]
            if fu.check_complete_files(output_file_list):
                fu.log('Restart is enabled, this step: %s will the skipped' % self.step, out_log, self.global_log)
                return 0

        cmd = [self.gmx_path, 'editconf',
               '-f', self.input_gro_path,
               '-o', self.output_gro_path,
               '-d', str(self.distance_to_molecule),
               '-bt', self.box_type]

        if self.docker_path:
            fu.log('Docker execution enabled', out_log)
            unique_dir = os.path.abspath(fu.create_unique_dir())
            shutil.copy2(self.input_gro_path, unique_dir)
            docker_input_gro_path = os.path.join(self.docker_volume_path, os.path.basename(self.input_gro_path))
            docker_output_gro_path = os.path.join(self.docker_volume_path, os.path.basename(self.output_gro_path))
            cmd = [self.docker_path, 'run',
                   '-v', unique_dir+':'+self.docker_volume_path,
                   '--user', str(os.getuid()),
                   self.docker_image,
                   self.gmx_path, 'editconf',
                   '-f', docker_input_gro_path,
                   '-o', docker_output_gro_path,
                   '-d', str(self.distance_to_molecule),
                   '-bt', self.box_type]

        if self.center_molecule:
            cmd.append('-c')
            fu.log('Centering molecule in the box.', out_log, self.global_log)

        fu.log("Distance of the box to molecule: %6.2f" % self.distance_to_molecule, out_log, self.global_log)
        fu.log("Box type: %s" % self.box_type, out_log, self.global_log)

        new_env = None
        if self.gmxlib:
            new_env = os.environ.copy()
            new_env['GMXLIB'] = self.gmxlib

        returncode = cmd_wrapper.CmdWrapper(cmd, out_log, err_log, self.global_log, self.gmxlib).launch()

        if self.docker_path:
            shutil.copy2(os.path.join(unique_dir, os.path.basename(self.output_gro_path)), self.output_gro_path)

        if self.remove_tmp:
            fu.rm_file_list(tmp_files, out_log=out_log)

        return returncode

def main():
    parser = argparse.ArgumentParser(description="Wrapper of the GROMACS editconf module.", formatter_class=lambda prog: argparse.RawTextHelpFormatter(prog, width=99999))
    parser.add_argument('-c', '--config', required=False, help="This file can be a YAML file, JSON file or JSON string")
    parser.add_argument('--system', required=False, help="Check 'https://biobb-common.readthedocs.io/en/latest/system_step.html' for help")
    parser.add_argument('--step', required=False, help="Check 'https://biobb-common.readthedocs.io/en/latest/system_step.html' for help")

    #Specific args of each building block
    required_args = parser.add_argument_group('required arguments')
    required_args.add_argument('--input_gro_path', required=True)
    required_args.add_argument('--output_gro_path', required=True)

    args = parser.parse_args()
    config = args.config if args.config else None
    properties = settings.ConfReader(config=config, system=args.system).get_prop_dic()
    if args.step:
        properties = properties[args.step]

    #Specific call of each building block
    Editconf(input_gro_path=args.input_gro_path, output_gro_path=args.output_gro_path, properties=properties).launch()

if __name__ == '__main__':
    main()
