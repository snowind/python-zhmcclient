#!/usr/bin/env python
# Copyright 2016 IBM Corp. All Rights Reserved.
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

"""
Unit tests for _session module.
"""

from __future__ import absolute_import, print_function

import unittest
import requests
import requests_mock
import time
import json

from zhmcclient import Session, ParseError, Job, HTTPError, TimeoutError


class SessionTests(unittest.TestCase):
    """
    Test the ``Session`` class.
    """

    # TODO: Test Session.get() in all variations (including errors)
    # TODO: Test Session.post() in all variations (including errors)
    # TODO: Test Session.delete() in all variations (including errors)

    @staticmethod
    def mock_server_1(m):
        """
        Set up the mocked responses for a simple HMC server that supports
        logon and logoff.
        """
        m.register_uri('POST', '/api/sessions',
                       json={'api-session': 'fake-session-id'},
                       headers={'X-Request-Id': 'fake-request-id'})
        m.register_uri('DELETE', '/api/sessions/this-session',
                       headers={'X-Request-Id': 'fake-request-id'},
                       status_code=204)

    def test_init(self):
        """Test initialization of Session object."""

        session = Session('fake-host', 'fake-user', 'fake-pw')

        self.assertEqual(session.host, 'fake-host')
        self.assertEqual(session.userid, 'fake-user')
        self.assertEqual(session._password, 'fake-pw')
        base_url = 'https://' + session.host + ':6794'
        self.assertEqual(session.base_url, base_url)
        self.assertTrue('Content-type' in session.headers)
        self.assertTrue('Accept' in session.headers)
        self.assertEqual(len(session.headers), 2)
        self.assertIsNone(session.session_id)
        self.assertTrue('X-API-Session' not in session.headers)
        self.assertIsNone(session.session)

    @requests_mock.mock()
    def test_logon_logoff(self, m):
        """Test logon and logoff; this uses post() and delete()."""

        self.mock_server_1(m)

        session = Session('fake-host', 'fake-user', 'fake-pw')

        self.assertIsNone(session.session_id)
        self.assertTrue('X-API-Session' not in session.headers)
        self.assertIsNone(session.session)

        logged_on = session.is_logon()

        self.assertFalse(logged_on)

        session.logon()

        self.assertEqual(session.session_id, 'fake-session-id')
        self.assertTrue('X-API-Session' in session.headers)
        self.assertTrue(isinstance(session.session, requests.Session))

        logged_on = session.is_logon()

        self.assertTrue(logged_on)

        session.logoff()

        self.assertIsNone(session.session_id)
        self.assertTrue('X-API-Session' not in session.headers)
        self.assertIsNone(session.session)

        logged_on = session.is_logon()

        self.assertFalse(logged_on)

    def _do_parse_error_logon(self, m, json_content, exp_msg_pattern, exp_line,
                              exp_col):
        """
        Perform a session logon, and mock the provided (invalid) JSON content
        for the response so that a JSON parsing error is triggered.

        Assert that this is surfaced via a `zhmcclient.ParseError` exception,
        with the expected message (as a regexp pattern), line and column.
        """

        m.register_uri('POST', '/api/sessions',
                       content=json_content,
                       headers={'X-Request-Id': 'fake-request-id'})

        session = Session('fake-host', 'fake-user', 'fake-pw')

        exp_pe_pattern = r"Parse error in returned JSON: %s" % exp_msg_pattern

        with self.assertRaisesRegexp(ParseError, exp_pe_pattern) as cm:
            session.logon()
        self.assertEqual(cm.exception.line, exp_line)
        self.assertEqual(cm.exception.column, exp_col)

    @requests_mock.mock()
    def test_logon_error_invalid_delim(self, m):
        """
        Logon with invalid JSON response that has an invalid delimiter.
        """
        json_content = b'{\n"api-session"; "fake-session-id"\n}'
        exp_msg_pattern = r"Expecting ':' delimiter"
        exp_line = 2
        exp_col = 14
        self._do_parse_error_logon(m, json_content, exp_msg_pattern, exp_line,
                                   exp_col)

    @requests_mock.mock()
    def test_logon_error_invalid_quotes(self, m):
        """
        Logon with invalid JSON response that incorrectly uses single quotes.
        """
        json_content = b'{\'api-session\': \'fake-session-id\'}'
        exp_msg_pattern = r"Expecting property name enclosed in double quotes"
        exp_line = 1
        exp_col = 2
        self._do_parse_error_logon(m, json_content, exp_msg_pattern, exp_line,
                                   exp_col)

    @requests_mock.mock()
    def test_logon_error_extra_closing(self, m):
        """
        Logon with invalid JSON response that has an extra closing brace.
        """
        json_content = b'{"api-session": "fake-session-id"}}'
        exp_msg_pattern = r"Extra data"
        exp_line = 1
        exp_col = 35
        self._do_parse_error_logon(m, json_content, exp_msg_pattern, exp_line,
                                   exp_col)

    def test_get_notification_topics(self):
        """
        This tests the 'Get Notification Topics' operation.
        """
        session = Session('fake-host', 'fake-user', 'fake-id')
        with requests_mock.mock() as m:
            # Because logon is deferred until needed, we perform it
            # explicitly in order to keep mocking in the actual test simple.
            m.post('/api/sessions', json={'api-session': 'fake-session-id'})
            session.logon()
            gnt_uri = "/api/sessions/operations/get-notification-topics"
            gnt_result = {
                "topics": [
                    {
                        'topic-name': 'ensadmin.145',
                        'topic-type': 'object-notification',
                    },
                    {
                        'topic-name': 'ensadmin.145job',
                        'topic-type': 'job-notification',
                    },
                    {
                        'topic-name': 'ensadmin.145aud',
                        'topic-type': 'audit-notification',
                    },
                    {
                        'topic-name': 'ensadmin.145sec',
                        'topic-type': 'security-notification',
                    }
                ]
            }
            m.get(gnt_uri, json=gnt_result)

            result = session.get_notification_topics()

            self.assertEqual(result, gnt_result['topics'])

            m.delete('/api/sessions/this-session', status_code=204)

            session.logoff()

    def test_get_error_html_1(self):
        """
        This tests a dummy GET with a 500 response with HTML content.
        """
        session = Session('fake-host', 'fake-user', 'fake-id')
        with requests_mock.mock() as m:
            get_uri = "/api/version"
            get_resp_status = 500
            get_resp_content_type = 'text/html; charset=ISO-5589-1'
            get_resp_headers = {
                'content-type': get_resp_content_type,
            }
            get_resp_content = u"""\
<!doctype html public "-//IETF//DTD HTML 2.0//EN">\
 <html>\
<head>\
<title>Console Internal Error</title>\
 <link href="/skin/HMCskin.css" rel="stylesheet" type="text/css"/>\
</head>\
 <body>\
<h1>Console Internal Error</h1>\
<br><hr size="1" noshade>\
<h2>Details:</h2>\
<p><br>HTTP status code: 500\
<p><br>The server encountered an internal error that prevented it from\
 fulfilling this request.\
<p><br>\
<pre>javax.servlet.ServletException: Web Services are not enabled.
\tat com.ibm.hwmca.fw.api.ApiServlet.execute(ApiServlet.java:135)
\t. . .
</pre>\
<hr size="1" noshade>\
</body>\
</html>"""
            m.get(get_uri, text=get_resp_content, headers=get_resp_headers,
                  status_code=get_resp_status)

            # The following expected results reflect what is done in
            # _session._result_object().

            exp_reason = 999
            exp_message = \
                "Console Internal Error: \\n" \
                "HTTP status code: 500\\n" \
                "The server encountered an internal error that prevented it " \
                "from fulfilling this request.\\n" \
                "<pre>javax.servlet.ServletException: Web Services are not " \
                "enabled.\\n" \
                "\tat com.ibm.hwmca.fw.api.ApiServlet.execute(ApiServlet." \
                "java:135)\\n" \
                "\t. . .\\n" \
                "</pre>"

            with self.assertRaises(HTTPError) as cm:
                session.get(get_uri, logon_required=False)
            exc = cm.exception

            self.assertEqual(exc.http_status, get_resp_status)
            self.assertEqual(exc.reason, exp_reason)
            self.assertEqual(exc.message, exp_message)
            self.assertTrue(exc.request_uri.endswith(get_uri))
            self.assertEqual(exc.request_method, 'GET')


class JobTests(unittest.TestCase):
    """
    Test the ``Job`` class.
    """

    job_uri = '/api/jobs/fake-job-uri'

    @staticmethod
    def mock_server_1(m):
        """
        Set up the mocked responses for a simple HMC server that supports
        logon, logoff.
        """
        m.register_uri('POST', '/api/sessions',
                       json={'api-session': 'fake-session-id'},
                       headers={'X-Request-Id': 'fake-request-id'})
        m.register_uri('DELETE', '/api/sessions/this-session',
                       headers={'X-Request-Id': 'fake-request-id'},
                       status_code=204)

    def test_init(self):
        """Test initialization of Job object."""
        session = Session('fake-host', 'fake-user', 'fake-pw')

        job = Job(session, self.job_uri)

        self.assertEqual(job.uri, self.job_uri)
        self.assertEqual(job.session, session)

    def test_check_incomplete(self):
        """Test check_for_completion() with incomplete job."""
        with requests_mock.mock() as m:
            self.mock_server_1(m)
            session = Session('fake-host', 'fake-user', 'fake-pw')
            job = Job(session, self.job_uri)
            query_job_status_result = {
                'status': 'running',
            }
            m.get(self.job_uri, json=query_job_status_result)
            m.delete(self.job_uri)

            job_status, oper_result = job.check_for_completion()

            self.assertEqual(job_status, 'running')
            self.assertIsNone(oper_result)

    def test_check_complete_success_noresult(self):
        """Test check_for_completion() with successful complete job without
        result."""
        with requests_mock.mock() as m:
            self.mock_server_1(m)
            session = Session('fake-host', 'fake-user', 'fake-pw')
            job = Job(session, self.job_uri)
            query_job_status_result = {
                'status': 'complete',
                'job-status-code': 200,
                # 'job-reason-code' omitted because HTTP status good
                # 'job-results' is optional and is omitted
            }
            m.get(self.job_uri, json=query_job_status_result)
            m.delete(self.job_uri)

            job_status, oper_result = job.check_for_completion()

            self.assertEqual(job_status, 'complete')
            self.assertIsNone(oper_result)

    def test_check_complete_success_result(self):
        """Test check_for_completion() with successful complete job with a
        result."""
        with requests_mock.mock() as m:
            self.mock_server_1(m)
            session = Session('fake-host', 'fake-user', 'fake-pw')
            job = Job(session, self.job_uri)
            exp_oper_result = {
                'foo': 'bar',
            }
            query_job_status_result = {
                'status': 'complete',
                'job-status-code': 200,
                # 'job-reason-code' omitted because HTTP status good
                'job-results': exp_oper_result,
            }
            m.get(self.job_uri, json=query_job_status_result)
            m.delete(self.job_uri)

            job_status, oper_result = job.check_for_completion()

            self.assertEqual(job_status, 'complete')
            self.assertEqual(oper_result, exp_oper_result)

    def test_check_complete_error(self):
        """Test check_for_completion() with complete job in error."""
        with requests_mock.mock() as m:
            self.mock_server_1(m)
            session = Session('fake-host', 'fake-user', 'fake-pw')
            job = Job(session, self.job_uri)
            error_result = {
                'message': 'bla',
            }
            query_job_status_result = {
                'status': 'complete',
                'job-status-code': 500,
                'job-reason-code': 42,
                'job-results': error_result,
            }
            m.get(self.job_uri, json=query_job_status_result)
            m.delete(self.job_uri)

            with self.assertRaises(HTTPError) as cm:
                job_status, oper_result = job.check_for_completion()

            self.assertEqual(cm.exception.http_status, 500)
            self.assertEqual(cm.exception.reason, 42)
            self.assertEqual(cm.exception.message, 'bla')

    def test_wait_complete1_success_result(self):
        """Test wait_for_completion() with successful complete job with a
        result."""
        with requests_mock.mock() as m:
            self.mock_server_1(m)
            session = Session('fake-host', 'fake-user', 'fake-pw')
            job = Job(session, self.job_uri)
            exp_oper_result = {
                'foo': 'bar',
            }
            query_job_status_result = {
                'status': 'complete',
                'job-status-code': 200,
                # 'job-reason-code' omitted because HTTP status good
                'job-results': exp_oper_result,
            }
            m.get(self.job_uri, json=query_job_status_result)
            m.delete(self.job_uri)

            oper_result = job.wait_for_completion()

            self.assertEqual(oper_result, exp_oper_result)

    def test_wait_complete3_success_result(self):
        """Test wait_for_completion() with successful complete job with a
        result."""
        with requests_mock.mock() as m:
            self.mock_server_1(m)
            session = Session('fake-host', 'fake-user', 'fake-pw')
            job = Job(session, self.job_uri)
            exp_oper_result = {
                'foo': 'bar',
            }
            m.get(self.job_uri,
                  [
                      {'text': result_running_callback},
                      {'text': result_complete_callback},
                  ])
            m.delete(self.job_uri)

            oper_result = job.wait_for_completion()

            self.assertEqual(oper_result, exp_oper_result)

    def test_wait_complete3_timeout(self):
        """Test wait_for_completion() with timeout."""
        with requests_mock.mock() as m:
            self.mock_server_1(m)
            session = Session('fake-host', 'fake-user', 'fake-pw')
            job = Job(session, self.job_uri)
            m.get(self.job_uri,
                  [
                      {'text': result_running_callback},
                      {'text': result_running_callback},
                      {'text': result_complete_callback},
                  ])
            m.delete(self.job_uri)

            # Here we provoke a timeout, by setting the timeout to less than
            # the time it would take to return the completed job status.
            # The time it would take is the sum of the following:
            # - 2 * 1 s (1 s is the sleep time in Job.wait_for_completion(),
            #   and this happens before each repeated status retrieval)
            # - 3 * 1 s (1 s is the sleep time in result_*_callback() in this
            #   module, and this happens in each mocked status retrieval)
            # Because status completion is given priority over achieving the
            # timeout duration, the timeout value needed to provoke the
            # timeout exception needs to be shorter by the last status
            # retrieval (the one that completes the job), so 3 s is the
            # boundary for the timeout value.
            timeout = 2.9
            try:
                start_time = time.time()
                job.wait_for_completion(timeout=timeout)
                duration = time.time() - start_time
                self.fail("No TimeoutError raised. Actual duration: %s s, "
                          "timeout: %s s" % (duration, timeout))
            except TimeoutError as exc:
                msg = exc.args[0]
                self.assertTrue(msg.startswith(
                    "Waiting for completion of job"))


def result_running_callback(request, context):
    job_result_running = {
        'status': 'running',
    }
    time.sleep(1)
    return json.dumps(job_result_running)


def result_complete_callback(request, context):
    exp_oper_result = {
        'foo': 'bar',
    }
    job_result_complete = {
        'status': 'complete',
        'job-status-code': 200,
        # 'job-reason-code' omitted because HTTP status good
        'job-results': exp_oper_result,
    }
    time.sleep(1)
    return json.dumps(job_result_complete)


if __name__ == '__main__':
    unittest.main()
