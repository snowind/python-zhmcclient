# Copyright 2019 IBM Corp. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import pytest
import zhmcclient
from zhmcclient.testutils.hmc_definitions import HMCDefinitionFile, \
    HMCDefinition

# HMC nickname or HMC group nickname in HMC definition file
TESTHMC = os.getenv('TESTHMC', 'default')
HMC_DEF_LIST = HMCDefinitionFile().list_hmcs(TESTHMC)


def fixtureid_hmc_definition(fixture_value):
    """
    Return a fixture ID to be used by pytest, for fixture `hmc_definition()`.

    Parameters:
      * fixture_value (HMCDefinition): The HMC definition of the HMC the test
        runs against.
    """
    hd = fixture_value
    assert isinstance(hd, HMCDefinition)
    return "hmc_definition={}".format(hd.nickname)


@pytest.fixture(
    params=HMC_DEF_LIST,
    scope='module',
    ids=fixtureid_hmc_definition
)
def hmc_definition(request):
    """
    Fixture representing the set of HMC definitions to use for the end2end
    tests.

    Returns the `HMCDefinition` object of each HMC to test against.
    """
    return request.param


@pytest.fixture(
    scope='module'
)
def hmc_session(request, hmc_definition):
    """
    Pytest fixture representing the set of `zhmcclient.Session` objects to use
    for the end2end tests.

    Because the `hmc_definition` parameter of this fixture is again a fixture,
    `hmc_definition` needs to be imported as well when this fixture is used.

    Returns a `zhmcclient.Session` object that is logged on to the HMC.

    Upon teardown, the `zhmcclient.Session` object is logged off.
    """
    hd = hmc_definition

    # We use the cached skip reason from previous attempts
    skip_msg = getattr(hd, 'skip_msg', None)
    if skip_msg:
        pytest.skip("Skip reason from earlier attempt: {0}".format(skip_msg))

    # Creating a session does not interact with the HMC (logon is deferred)
    session = zhmcclient.Session(hd.hmc_host, hd.hmc_userid, hd.hmc_password)

    # Check access to the HMC
    try:
        session.logon()
    except zhmcclient.Error as exc:
        msg = "Cannot log on to HMC {0} at {1} due to {2}: {3}". \
            format(hd.nickname, hd.hmc_host, exc.__class__.__name__, exc)
        hd.skip_msg = msg
        pytest.skip(msg)

    hd.skip_msg = None
    session.hmc_definition = hd

    yield session

    session.logoff()
