#
# Copyright (c)      2019 Triad National Security, LLC
#                         All rights reserved.
#
# This file is part of the bueno project. See the LICENSE file at the
# top-level directory of this distribution for more information.
#

'''
The build service module.
'''

from bueno.core import service
from bueno.core import utils
from bueno.core import opsys

from bueno.build import builder

import yaml


class impl(service.Service):
    '''
    Implements the build service.
    '''
    class _defaults:
        '''
        Convenience container for build service defaults.
        '''
        # TODO(skg) Add a proper service description.
        desc = 'The build service builds containers.'

        builder = 'charliecloud'

    def __init__(self, argv):
        super().__init__(impl._defaults.desc, argv)

        self.stime = utils.now()
        self.etime = None

        self.builder = None

    def _addargs(self):
        self.argp.add_argument(
            '--builder',
            type=str,
            help='Specifies the container builder to use. '
                 'Default: {}'.format(impl._defaults.builder),
            default=impl._defaults.builder,
            choices=builder.Factory.available(),
            required=False
        )

    def _populate_service_config(self):
        self.confd['Configuration'] = vars(self.args)

    def _populate_env_config(self):
        self.confd['Environment'] = {
            'kernel': opsys.kernel(),
            'kernel release': opsys.kernelrel(),
            'hostname': opsys.hostname(),
            'os release': opsys.pretty_name()
        }

    # TODO(skg) Add more configuration info.
    def _emit_config(self):
        # First build up the dictionary containing the configuration used.
        self._populate_service_config()
        self._populate_env_config()
        # Then print it out in YAML format.
        print(utils.chomp(yaml.dump(self.confd, default_flow_style=False)))

    def _do_build(self):
        self.builder = builder.Factory.build(self.args.builder)

    def start(self):
        print()
        print('# Begin {} Configuration {}'.format(self.prog, self.stime))

        self._emit_config()
        self._do_build()

        self.etime = utils.now()
        print('# End {} Configuration {}'.format(self.prog, self.etime))
        print('# {} Time {}'.format(self.prog, self.etime - self.stime))
