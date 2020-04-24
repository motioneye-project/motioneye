
# Copyright (c) 2020 Vlsarro
# Copyright (c) 2013 Calin Crisan
# This file is part of motionEye.
#
# motionEye is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from motioneye import config
from motioneye import motionctl
from motioneye import settings
from motioneye import update
from motioneye import utils
from motioneye.handlers.base import BaseHandler


__all__ = ('MainHandler',)


class MainHandler(BaseHandler):
    def get(self):
        # additional config
        main_sections = config.get_additional_structure(camera=False, separators=True)[0]
        camera_sections = config.get_additional_structure(camera=True, separators=True)[0]

        motion_info = motionctl.find_motion()
        os_version = update.get_os_version()

        self.render('main.html',
                    frame=False,
                    motion_version=motion_info[1] if motion_info else '(none)',
                    os_version=' '.join(os_version),
                    enable_update=settings.ENABLE_UPDATE,
                    enable_reboot=settings.ENABLE_REBOOT,
                    add_remove_cameras=settings.ADD_REMOVE_CAMERAS,
                    main_sections=main_sections,
                    camera_sections=camera_sections,
                    hostname=settings.SERVER_NAME,
                    title=self.get_argument('title', None),
                    admin_username=config.get_main().get('@admin_username'),
                    has_h264_omx_support=motionctl.has_h264_omx_support(),
                    has_h264_v4l2m2m_support=motionctl.has_h264_v4l2m2m_support(),
                    has_h264_nvenc_support=motionctl.has_h264_nvenc_support(),
                    has_h264_nvmpi_support=motionctl.has_h264_nvmpi_support(),
                    has_hevc_nvenc_support=motionctl.has_hevc_nvenc_support(),
                    has_hevc_nvmpi_support=motionctl.has_hevc_nvmpi_support(),
                    has_h264_qsv_support=motionctl.has_h264_qsv_support(),
                    has_hevc_qsv_support=motionctl.has_hevc_qsv_support(),
                    has_motion=bool(motionctl.find_motion()[0]),
                    mask_width=utils.MASK_WIDTH)
