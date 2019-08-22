#
# Copyright (c)      2019 Triad National Security, LLC
#                         All rights reserved.
#
# This file is part of the bueno project. See the LICENSE file at the
# top-level directory of this distribution for more information.
#

'''
The run service module.
'''

from bueno.core import cntrimg
from bueno.core import service

from bueno.public import experiment
from bueno.public import logger
from bueno.public import metadata
from bueno.public import opsys
from bueno.public import utils

import argparse
import copy
import importlib.util
import os
import sys


class _Runner:
    @staticmethod
    def run(argv):
        '''
        Loads and executes the run program specified at argv[0], passing along
        all program-specific arguments to the program (argv).
        '''
        argz = argv[0]
        # Stash the program.
        metadata.add_asset(metadata.FileAsset(argz))
        # Import and run the specified program. argz passed twice for nicer
        # error messages when a user specifies a bogus program.
        spec = importlib.util.spec_from_file_location(argz, argz)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        # Make sure the experiment is setup properly. We can do this only after
        # the module has been loaded.
        experiment._TheExperiment().sanity()
        # Save cwd so we can restore it after program execution.
        scwd = os.getcwd()
        try:
            # What's the specified program's cwd?
            pbase = os.path.dirname(argz)
            # cddir to base of given program so relative operations work
            # properly.
            os.chdir(pbase)
            mod.main(argv)
        finally:
            os.chdir(scwd)


class impl(service.Base):
    '''
    Implements the run service.
    '''
    class _defaults:
        '''
        Convenience container for run service defaults.
        '''
        desc = 'The run service runs programs and can serve ' \
               'as a dispatch service to container activators.'
        # Path to save any generated files.
        output_path = os.getcwd()
        # The image activator to use by default.
        imgactvtr = 'charliecloud'

    class ProgramAction(argparse.Action):
        '''
        Custom action class used for 'program' argument structure verification.
        '''
        def __init__(self, option_strings, dest, nargs, **kwargs):
            super().__init__(option_strings, dest, nargs, **kwargs)

        def __call__(self, parser, namespace, values, option_string=None):
            if len(values) == 0:
                help = '{} requires at least one argument (none provided).\n'\
                       'Please provide a path to the program you wish to run, '\
                       'optionally followed by program-specific arguments.'

                parser.error(help.format(option_string))
            # Capture and update values[0] to an absolute path.
            prog = values[0] = os.path.abspath(values[0])
            if not os.path.isfile(prog):
                es = '{} is not a file. Cannot continue.'.format(prog)
                parser.error(es.format(prog))

            setattr(namespace, self.dest, values)

    class ImageDirAction(argparse.Action):
        '''
        Custom action class used for 'image-dir' argument handling.
        '''
        def __init__(self, option_strings, dest, nargs=None, **kwargs):
            super().__init__(option_strings, dest, **kwargs)

        def __call__(self, parser, namespace, values, option_string=None):
            imgp = os.path.abspath(values)
            setattr(namespace, self.dest, imgp)

    class ImageActivatorAction(argparse.Action):
        '''
        Custom action class used for 'image-activator' argument handling.
        '''
        def __init__(self, option_strings, dest, nargs=None, **kwargs):
            # Store reference to imgdir_arg for later use.
            self.imgdir_arg = kwargs.pop('imgdir_arg')
            super().__init__(option_strings, dest, **kwargs)

        def __call__(self, parser, namespace, values, option_string=None):
            # Adjust image-dir options if the image activator is none.
            if values == 'none':
                self.imgdir_arg.required = False
                self.imgdir_arg.help = argparse.SUPPRESS
            setattr(namespace, self.dest, values)

    def __init__(self, argv):
        super().__init__(impl._defaults.desc, argv)

    def _addargs(self):
        self.argp.add_argument(
            '-o', '--output-path',
            type=str,
            help='Specifies the base output directory used for all '
                  'generated files. Default: {}'.format('PWD'),
            default=impl._defaults.output_path,
            required=False
        )

        imgdir_arg = self.argp.add_argument(
            '-i', '--image-dir',
            type=str,
            help='Specifies the base container image directory.',
            required=True,
            action=impl.ImageDirAction
        )

        self.argp.add_argument(
            '-a', '--image-activator',
            type=str,
            help='Specifies the image activator used to execute '
                 'commands within a container. '
                 'Default: {}'.format(impl._defaults.imgactvtr),
            default=impl._defaults.imgactvtr,
            choices=cntrimg.ImageActivatorFactory.available(),
            required=False,
            action=impl.ImageActivatorAction,
            imgdir_arg=imgdir_arg
        )

        self.argp.add_argument(
            '-p', '--program',
            # Consume the remaining arguments for program's use.
            nargs=argparse.REMAINDER,
            help='Specifies the program to run, optionally '
                 'followed by program-specific arguments.',
            required=True,
            action=impl.ProgramAction
        )

        # TODO(skg) Add --bind option.

    def _populate_service_config(self):
        # Remove program from output since it is reduntant and because we don't
        # know how it'll be parsed by the given program.
        tmpargs = copy.deepcopy(vars(self.args))
        tmpargs.pop('program')
        self.confd['Configuration'] = tmpargs
        metadata.add_asset(metadata.YAMLDictAsset(self.confd, 'run'))

    def _populate_sys_config(self):
        self.confd['Host'] = {
            'whoami': opsys.whoami(),
            'kernel': opsys.kernel(),
            'kernel_release': opsys.kernelrel(),
            'hostname': opsys.hostname(),
            'os_release': opsys.pretty_name()
        }

    def _populate_config(self):
        self._populate_service_config()
        self._populate_sys_config()

    # TODO(skg) Add more configuration info.
    def _emit_config(self):
        # First build up the dictionary containing the configuration used.
        self._populate_config()
        # Add to metadata assets stored to container image.
        metadata.add_asset(metadata.YAMLDictAsset(self.confd, 'environment'))
        # Then print it out in YAML format.
        utils.yamlp(self.confd, self.prog)

    def _run(self):
        # Setup image activator so that it is ready-to-go for the run.
        actvtr = self.args.image_activator
        imgdir = self.args.image_dir
        cntrimg.ImageActivatorFactory().build(actvtr, imgdir)

        pname = os.path.basename(self.args.program[0])
        logger.emlog('# Begin Program Output ({})'.format(pname))
        _Runner.run(self.args.program)
        logger.emlog('# End Program Output')

    def _getmetasubd(self):
        expn = experiment.name()
        return '{}-{}'.format(expn, utils.nows().replace(' ', '-'))

    def _write_metadata(self):
        base = self.args.output_path
        subd = self._getmetasubd()
        outp = os.path.join(base, subd)
        metadata.write(outp)
        logger.log('# Run Output Written to: {}'.format(outp))

    def start(self):
        logger.emlog('# Starting {} at {}'.format(self.prog, utils.nows()))
        logger.log('# $ {}\n'.format(' '.join(sys.argv)))

        stime = utils.now()
        try:
            self._emit_config()
            self._run()
        except Exception as e:
            estr = utils.ehorf()
            estr += 'What: {} error encountered.\n' \
                    'Why:  {}'.format(self.prog, e)
            estr += utils.ehorf()
            raise type(e)(estr)
        etime = utils.now()

        logger.log('# {} Time {}'.format(self.prog, etime - stime))
        logger.log('# {} Done {}'.format(self.prog, utils.nows()))

        self._write_metadata()
