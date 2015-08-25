# Copyright (c) 2015 Red Hat, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License.  You may obtain a copy
# of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations under
# the License.

import json
import uuid

import ddt
import mock
from oslo_utils import timeutils

from zaqar.tests.unit.transport.websocket import base
from zaqar.tests.unit.transport.websocket import utils as test_utils


@ddt.ddt
class ClaimsBaseTest(base.V1_1Base):

    config_file = "websocket_mongodb.conf"

    def setUp(self):
        super(ClaimsBaseTest, self).setUp()
        self.protocol = self.transport.factory()
        self.defaults = self.api.get_defaults()

        self.project_id = '7e55e1a7e'
        self.headers = {
            'Client-ID': str(uuid.uuid4()),
            'X-Project-ID': self.project_id
        }

        action = "queue_create"
        body = {"queue_name": "skittle"}
        req = test_utils.create_request(action, body, self.headers)

        with mock.patch.object(self.protocol, 'sendMessage') as msg_mock:
            self.protocol.onMessage(req, False)
            resp = json.loads(msg_mock.call_args[0][0])
            self.assertEqual(resp['headers']['status'], 201)

        action = "message_post"
        body = {"queue_name": "skittle",
                "messages": [
                    {'body': 239, 'ttl': 300},
                    {'body': {'key_1': 'value_1'}, 'ttl': 300},
                    {'body': [1, 3], 'ttl': 300},
                    {'body': 439, 'ttl': 300},
                    {'body': {'key_2': 'value_2'}, 'ttl': 300},
                    {'body': ['a', 'b'], 'ttl': 300},
                    {'body': 639, 'ttl': 300},
                    {'body': {'key_3': 'value_3'}, 'ttl': 300},
                    {'body': ["aa", "bb"], 'ttl': 300}]
                }

        send_mock = mock.Mock()
        self.protocol.sendMessage = send_mock

        req = test_utils.create_request(action, body, self.headers)

        self.protocol.onMessage(req, False)

        resp = json.loads(send_mock.call_args[0][0])
        self.assertEqual(resp['headers']['status'], 201)

    def tearDown(self):
        super(ClaimsBaseTest, self).tearDown()
        action = 'queue_delete'
        body = {'queue_name': 'skittle'}

        send_mock = mock.Mock()
        self.protocol.sendMessage = send_mock

        req = test_utils.create_request(action, body, self.headers)
        self.protocol.onMessage(req, False)

        resp = json.loads(send_mock.call_args[0][0])
        self.assertEqual(resp['headers']['status'], 204)

    @ddt.data('[', '[]', '.', '"fail"')
    def test_bad_claim(self, doc):
        action = "claim_create"
        body = doc

        send_mock = mock.Mock()
        self.protocol.sendMessage = send_mock

        req = test_utils.create_request(action, body, self.headers)
        self.protocol.onMessage(req, False)
        resp = json.loads(send_mock.call_args[0][0])
        self.assertEqual(resp['headers']['status'], 400)

        action = "claim_update"
        body = doc

        req = test_utils.create_request(action, body, self.headers)
        self.protocol.onMessage(req, False)
        resp = json.loads(send_mock.call_args[0][0])
        self.assertEqual(resp['headers']['status'], 400)

    def test_exceeded_claim(self):
        action = "claim_create"
        body = {"queue_name": "skittle",
                "ttl": 100,
                "grace": 60,
                "limit": 21}

        send_mock = mock.Mock()
        self.protocol.sendMessage = send_mock

        req = test_utils.create_request(action, body, self.headers)
        self.protocol.onMessage(req, False)
        resp = json.loads(send_mock.call_args[0][0])
        self.assertEqual(resp['headers']['status'], 400)

    @ddt.data((-1, -1), (59, 60), (60, 59), (60, 43201), (43201, 60))
    def test_unacceptable_ttl_or_grace(self, ttl_grace):
        ttl, grace = ttl_grace
        action = "claim_create"
        body = {"queue_name": "skittle",
                "ttl": ttl,
                "grace": grace}

        send_mock = mock.Mock()
        self.protocol.sendMessage = send_mock

        req = test_utils.create_request(action, body, self.headers)
        self.protocol.onMessage(req, False)
        resp = json.loads(send_mock.call_args[0][0])
        self.assertEqual(resp['headers']['status'], 400)

    @ddt.data(-1, 59, 43201)
    def test_unacceptable_new_ttl(self, ttl):
        claim = self._get_a_claim()

        action = "claim_update"
        body = {"queue_name": "skittle",
                "claim_id": claim['body']['claim_id'],
                "ttl": ttl}

        send_mock = mock.Mock()
        self.protocol.sendMessage = send_mock

        req = test_utils.create_request(action, body, self.headers)
        self.protocol.onMessage(req, False)
        resp = json.loads(send_mock.call_args[0][0])
        self.assertEqual(resp['headers']['status'], 400)

    def test_default_ttl_and_grace(self):
        action = "claim_create"
        body = {"queue_name": "skittle"}

        send_mock = mock.Mock()
        self.protocol.sendMessage = send_mock

        req = test_utils.create_request(action, body, self.headers)
        self.protocol.onMessage(req, False)
        resp = json.loads(send_mock.call_args[0][0])
        self.assertEqual(resp['headers']['status'], 201)

        action = "claim_get"
        body = {"queue_name": "skittle",
                "claim_id": resp['body']['claim_id']}

        req = test_utils.create_request(action, body, self.headers)
        self.protocol.onMessage(req, False)
        resp = json.loads(send_mock.call_args[0][0])

        self.assertEqual(resp['headers']['status'], 200)
        self.assertEqual(self.defaults.claim_ttl, resp['body']['ttl'])

    def test_lifecycle(self):
        # First, claim some messages
        action = "claim_create"
        body = {"queue_name": "skittle",
                "ttl": 100,
                "grace": 60}

        send_mock = mock.Mock()
        self.protocol.sendMessage = send_mock

        req = test_utils.create_request(action, body, self.headers)
        self.protocol.onMessage(req, False)
        resp = json.loads(send_mock.call_args[0][0])
        self.assertEqual(resp['headers']['status'], 201)
        claimed_messages = resp['body']['messages']
        claim_id = resp['body']['claim_id']

        # No more messages to claim
        body = {"queue_name": "skittle",
                "ttl": 100,
                "grace": 60}

        req = test_utils.create_request(action, body, self.headers)
        self.protocol.onMessage(req, False)
        resp = json.loads(send_mock.call_args[0][0])
        self.assertEqual(resp['headers']['status'], 204)

        # Listing messages, by default, won't include claimed, will echo
        action = "message_list"
        body = {"queue_name": "skittle",
                "echo": True}

        req = test_utils.create_request(action, body, self.headers)
        self.protocol.onMessage(req, False)
        resp = json.loads(send_mock.call_args[0][0])
        self.assertEqual(resp['headers']['status'], 200)
        self.assertEqual(resp['body']['messages'], [])

        # Listing messages, by default, won't include claimed, won't echo

        body = {"queue_name": "skittle",
                "echo": False}

        req = test_utils.create_request(action, body, self.headers)
        self.protocol.onMessage(req, False)
        resp = json.loads(send_mock.call_args[0][0])
        self.assertEqual(resp['headers']['status'], 200)
        self.assertEqual(resp['body']['messages'], [])

        # List messages, include_claimed, but don't echo

        body = {"queue_name": "skittle",
                "include_claimed": True,
                "echo": False}

        req = test_utils.create_request(action, body, self.headers)
        self.protocol.onMessage(req, False)
        resp = json.loads(send_mock.call_args[0][0])
        self.assertEqual(resp['headers']['status'], 200)
        self.assertEqual(resp['body']['messages'], [])

        # List messages with a different client-id and echo=false.
        # Should return some messages

        body = {"queue_name": "skittle",
                "echo": False}

        headers = {
            'Client-ID': str(uuid.uuid4()),
            'X-Project-ID': self.project_id
        }

        req = test_utils.create_request(action, body, headers)
        self.protocol.onMessage(req, False)
        resp = json.loads(send_mock.call_args[0][0])
        self.assertEqual(resp['headers']['status'], 200)

        # Include claimed messages this time, and echo

        body = {"queue_name": "skittle",
                "include_claimed": True,
                "echo": True}

        req = test_utils.create_request(action, body, self.headers)
        self.protocol.onMessage(req, False)
        resp = json.loads(send_mock.call_args[0][0])
        self.assertEqual(resp['headers']['status'], 200)
        self.assertEqual(len(resp['body']['messages']), len(claimed_messages))

        message_id_1 = resp['body']['messages'][0]['id']
        message_id_2 = resp['body']['messages'][1]['id']

        # Try to delete the message without submitting a claim_id
        action = "message_delete"
        body = {"queue_name": "skittle",
                "message_id": message_id_1}

        req = test_utils.create_request(action, body, self.headers)
        self.protocol.onMessage(req, False)
        resp = json.loads(send_mock.call_args[0][0])
        self.assertEqual(resp['headers']['status'], 403)

        # Delete the message and its associated claim
        body = {"queue_name": "skittle",
                "message_id": message_id_1,
                "claim_id": claim_id}

        req = test_utils.create_request(action, body, self.headers)
        self.protocol.onMessage(req, False)
        resp = json.loads(send_mock.call_args[0][0])
        self.assertEqual(resp['headers']['status'], 204)

        # Try to get it from the wrong project
        headers = {
            'Client-ID': str(uuid.uuid4()),
            'X-Project-ID': 'someproject'
        }

        action = "message_get"
        body = {"queue_name": "skittle",
                "message_id": message_id_2}
        req = test_utils.create_request(action, body, headers)
        self.protocol.onMessage(req, False)
        resp = json.loads(send_mock.call_args[0][0])
        self.assertEqual(resp['headers']['status'], 404)

        # Get the message
        action = "message_get"
        body = {"queue_name": "skittle",
                "message_id": message_id_2}
        req = test_utils.create_request(action, body, self.headers)
        self.protocol.onMessage(req, False)
        resp = json.loads(send_mock.call_args[0][0])
        self.assertEqual(resp['headers']['status'], 200)

        # Update the claim
        creation = timeutils.utcnow()
        action = "claim_update"
        body = {"queue_name": "skittle",
                "ttl": 60,
                "grace": 60,
                "claim_id": claim_id}
        req = test_utils.create_request(action, body, self.headers)
        self.protocol.onMessage(req, False)
        resp = json.loads(send_mock.call_args[0][0])
        self.assertEqual(resp['headers']['status'], 204)

        # Get the claimed messages (again)
        action = "claim_get"
        body = {"queue_name": "skittle",
                "claim_id": claim_id}
        req = test_utils.create_request(action, body, self.headers)
        self.protocol.onMessage(req, False)
        query = timeutils.utcnow()
        resp = json.loads(send_mock.call_args[0][0])
        self.assertEqual(resp['headers']['status'], 200)
        self.assertEqual(resp['body']['ttl'], 60)

        message_id_3 = resp['body']['messages'][0]['id']

        estimated_age = timeutils.delta_seconds(creation, query)
        self.assertTrue(estimated_age > resp['body']['age'])

        # Delete the claim
        action = "claim_delete"
        body = {"queue_name": "skittle",
                "claim_id": claim_id}
        req = test_utils.create_request(action, body, self.headers)
        self.protocol.onMessage(req, False)
        resp = json.loads(send_mock.call_args[0][0])
        self.assertEqual(resp['headers']['status'], 204)

        # Try to delete a message with an invalid claim ID
        action = "message_delete"
        body = {"queue_name": "skittle",
                "message_id": message_id_3,
                "claim_id": claim_id}

        req = test_utils.create_request(action, body, self.headers)
        self.protocol.onMessage(req, False)
        resp = json.loads(send_mock.call_args[0][0])
        self.assertEqual(resp['headers']['status'], 400)

        # Make sure it wasn't deleted!
        action = "message_get"
        body = {"queue_name": "skittle",
                "message_id": message_id_2}
        req = test_utils.create_request(action, body, self.headers)
        self.protocol.onMessage(req, False)
        resp = json.loads(send_mock.call_args[0][0])
        self.assertEqual(resp['headers']['status'], 200)

        # Try to get a claim that doesn't exist
        action = "claim_get"
        body = {"queue_name": "skittle",
                "claim_id": claim_id}
        req = test_utils.create_request(action, body, self.headers)
        self.protocol.onMessage(req, False)
        resp = json.loads(send_mock.call_args[0][0])
        self.assertEqual(resp['headers']['status'], 404)

        # Try to update a claim that doesn't exist
        action = "claim_update"
        body = {"queue_name": "skittle",
                "ttl": 60,
                "grace": 60,
                "claim_id": claim_id}
        req = test_utils.create_request(action, body, self.headers)
        self.protocol.onMessage(req, False)
        resp = json.loads(send_mock.call_args[0][0])
        self.assertEqual(resp['headers']['status'], 404)

    def test_post_claim_nonexistent_queue(self):
        action = "claim_create"
        body = {"queue_name": "nonexistent",
                "ttl": 100,
                "grace": 60}

        send_mock = mock.Mock()
        self.protocol.sendMessage = send_mock

        req = test_utils.create_request(action, body, self.headers)
        self.protocol.onMessage(req, False)
        resp = json.loads(send_mock.call_args[0][0])
        self.assertEqual(resp['headers']['status'], 204)

    def test_get_claim_nonexistent_queue(self):
        action = "claim_get"
        body = {"queue_name": "nonexistent",
                "claim_id": "aaabbbba"}

        send_mock = mock.Mock()
        self.protocol.sendMessage = send_mock

        req = test_utils.create_request(action, body, self.headers)
        self.protocol.onMessage(req, False)
        resp = json.loads(send_mock.call_args[0][0])
        self.assertEqual(resp['headers']['status'], 404)

    def _get_a_claim(self):
        action = "claim_create"
        body = {"queue_name": "skittle",
                "ttl": 100,
                "grace": 60}

        send_mock = mock.Mock()
        self.protocol.sendMessage = send_mock

        req = test_utils.create_request(action, body, self.headers)
        self.protocol.onMessage(req, False)
        resp = json.loads(send_mock.call_args[0][0])
        self.assertEqual(resp['headers']['status'], 201)

        return resp
