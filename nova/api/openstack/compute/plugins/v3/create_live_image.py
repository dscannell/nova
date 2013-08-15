#   Copyright 2011 OpenStack Foundation
#
#   Licensed under the Apache License, Version 2.0 (the "License"); you may
#   not use this file except in compliance with the License. You may obtain
#   a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#   WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#   License for the specific language governing permissions and limitations
#   under the License.

import os

import webob
from webob import exc

from nova.api.openstack import common
from nova.api.openstack.compute import servers
from nova.api.openstack import extensions
from nova.api.openstack import wsgi
from nova import compute
from nova import exception
from nova.openstack.common.gettextutils import _
from nova.openstack.common import log as logging


LOG = logging.getLogger(__name__)

ALIAS = 'os-create-live-image'
authorize = extensions.extension_authorizer('compute', 'v3:%s' % ALIAS)


class CreateLiveImageController(wsgi.Controller):
    def __init__(self, *args, **kwargs):
        super(CreateLiveImageController, self).__init__(*args, **kwargs)
        self.compute_api = compute.API()

    def _get_instance(self, context, instance_id):
        try:
            return self.compute_api.get(context, instance_id,
                                        want_objects=True)
        except exception.InstanceNotFound as e:
            raise exc.HTTPNotFound(explanation=e.format_message())

    @extensions.expected_errors((404, 409))
    @wsgi.response(202)
    @wsgi.serializers(xml=servers.FullServerTemplate)
    @wsgi.action('os-createLiveImage')
    def _live_snapshot(self, req, id, body):
        """Live-snapshot a server instance."""
        context = req.environ['nova.context']
        authorize(context)
        entity = body.get("os-createLiveImage", {})

        image_name = entity.get("name")

        if not image_name:
            msg = _("os-createLiveImage entity requires name attribute")
            raise exc.HTTPBadRequest(explanation=msg)

        props = {}
        metadata = entity.get('metadata', {})
        common.check_img_metadata_properties_quota(context, metadata)
        try:
            props.update(metadata)
        except ValueError:
            msg = _("Invalid metadata")
            raise exc.HTTPBadRequest(explanation=msg)

        try:
            instance = self.compute_api.get(context, id)
        except exception.NotFound:
            msg = _("Instance could not be found")
            raise exc.HTTPNotFound(explanation=msg)

        bdms = self.compute_api.get_instance_bdms(context, instance)
        try:
            if self.compute_api.is_volume_backed_instance(context, instance,
                                                          bdms):
                msg = _("Live snapshot of volume backed instances not allowed")
                raise exc.HTTPBadRequest(explanation=msg)
            else:
                image = self.compute_api.live_snapshot(context,
                    instance,
                    image_name,
                    extra_properties=props)
        except exception.InstanceInvalidState as state_error:
            common.raise_http_conflict_for_instance_invalid_state(state_error,
                'os-liveSnapshot')
        except exception.PolicyNotAuthorized:
            raise
        except Exception:
            LOG.exception(_("compute.api::live_snapshot failure"))
            raise exc.HTTPUnprocessableEntity()

        # build location of newly-created image entity
        image_id = str(image['id'])
        image_ref = os.path.join(req.application_url,
            context.project_id,
            'images',
            image_id)

        resp = webob.Response(status_int=202)
        resp.headers['Location'] = image_ref
        return resp


class Create_live_image(extensions.V3APIExtensionBase):
    """Extension to live-snaphot an instance.

    A live snapshot is a bootable image including memory and processor state.
    """

    name = "CreateLiveImage"
    alias = ALIAS
    namespace = ("http://docs.openstack.org/compute/ext/"
                 "os-create-live-image/api/v2")
    version = 1

    def get_controller_extensions(self):
        controller = CreateLiveImageController()
        extension = extensions.ControllerExtension(self, 'servers', controller)
        return [extension]

    def get_resources(self):
        return []
