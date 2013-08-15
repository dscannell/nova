# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import uuid

from webob import exc

from nova.api.openstack.compute.contrib import create_live_image
from nova import db
from nova import exception
from nova.openstack.common import policy
from nova import test
from nova.tests.api.openstack import fakes
from nova.tests import fake_instance


class CreateLiveImageTest(test.TestCase):
    def setUp(self):
        super(CreateLiveImageTest, self).setUp()
        self.controller = create_live_image.CreateLiveImageController()

    def test_create_live_image_restricted_by_role(self):
        rules = policy.Rules({'compute_extension:create-live-image':
                              policy.parse_rule('role:admin')})
        policy.set_rules(rules)

        req = fakes.HTTPRequest.blank('/v2/123/servers/12/'
                                      'os-create-live-image')
        self.assertRaises(exception.NotAuthorized,
                self.controller._live_snapshot, req, str(uuid.uuid4()), {})

    def open_policy(self):
        rules = policy.Rules({'compute:get': policy.parse_rule(''),
                              'compute:live_snapot': policy.parse_rule(''),
                              'compute_extension:create-live-image':
                                  policy.parse_rule('')})
        policy.set_rules(rules)

    def stub_instance_get_by_uuid(self, project_suffix='',
                                  image_ref=str(uuid.uuid4())):
        def fake_instance_get_by_uuid(context, instance_id,
                                      columns_to_join=None):
            return fake_instance.fake_db_instance(
                **{'name': 'fake', 'image_ref': image_ref,
                   'project_id': '%s%s' % (context.project_id, project_suffix)
                })

        self.stubs.Set(db, 'instance_get_by_uuid', fake_instance_get_by_uuid)

    def test_create_live_image_allowed(self):
        self.open_policy()
        self.stub_instance_get_by_uuid(project_suffix='_unequal')

        req = fakes.HTTPRequest.blank('/v2/123/servers/12/'
                                      'os-create-live-iamge')
        body = {'os-createLiveImage': {'name': 'create-live-image-test'}}
        self.assertRaises(exception.NotAuthorized,
                self.controller._live_snapshot, req, str(uuid.uuid4()), body)

    def test_create_live_image_no_name(self):
        self.open_policy()
        self.stub_instance_get_by_uuid()

        req = fakes.HTTPRequest.blank('/v2/123/servers/12/'
                                      'os-create-live-iamge')
        body = {'os-createLiveImage': {}}
        self.assertRaises(exc.HTTPBadRequest,
            self.controller._live_snapshot, req, str(uuid.uuid4()), body)

    def test_create_live_image_bad_metadata(self):
        self.open_policy()
        self.stub_instance_get_by_uuid()

        req = fakes.HTTPRequest.blank('/v2/123/servers/12/'
                                      'os-create-live-iamge')
        body = {'os-createLiveImage': {'name': 'create-live-image-test',
                                       'metadata': 'should_be_dict'}}
        self.assertRaises(exc.HTTPBadRequest,
            self.controller._live_snapshot, req, str(uuid.uuid4()), body)

    def test_create_live_image_volume_backed(self):
        self.open_policy()
        self.stub_instance_get_by_uuid(image_ref=None)

        req = fakes.HTTPRequest.blank('/v2/123/servers/12/'
                                      'os-create-live-iamge')
        body = {'os-createLiveImage': {'name': 'create-live-image-test'}}
        self.assertRaises(exc.HTTPUnprocessableEntity,
            self.controller._live_snapshot, req, str(uuid.uuid4()), body)
