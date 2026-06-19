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

from motioneye.handlers.base import BaseHandler, invalidate_session

__all__ = ('LogoutHandler',)


class LogoutHandler(BaseHandler):
    def post(self):
        # Clear the session cookie
        self.clear_cookie('user')

        # Invalidate the session id stored in the secure cookie
        session_id = self.get_secure_cookie('user')
        if session_id:
            session_id = (
                session_id.decode('utf-8')
                if isinstance(session_id, bytes)
                else session_id
            )
            invalidate_session(session_id)
