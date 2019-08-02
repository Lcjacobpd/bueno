#
# Copyright (c)      2019 Triad National Security, LLC
#                         All rights reserved.
#
# This file is part of the bueno project. See the LICENSE file at the
# top-level directory of this distribution for more information.
#

from bueno.public import utils
from bueno.public import logger
from bueno.public import container
from bueno.public import experiment

import time

experiment.name('nbody')


def main(argv):
    logger.log('# Experiment: {}'.format(experiment.name()))

    prun = 'mpiexec'
    app = '/nbody/nbody-mpi'

    # The seemingly strange replacement of the second set of brackets with '{}'
    # allows us to first format the string with arguments and then generate
    # strings with values passed to -n from the output of range().
    runcmds = experiment.generate(
        '{} -n {} {}'.format(prun, '{}', app),
        range(2, 5)
    )

    etimes = list()
    for r in runcmds:
        stime = utils.now()
        container.run(r)
        etime = utils.now()
        telapsed = etime - stime
        etimes.append(telapsed)
        logger.log('# Execution Time: {}\n'.format(telapsed))
        # Take a break between runs.
        time.sleep(1)

    logger.log('# Report')
    logger.log('# Command, Execution Time')
    for i in zip(runcmds, etimes):
        logger.log('{}, {}'.format(*i))