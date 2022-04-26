
var refreshDisabled = false;


    /* camera frame */

function setupCameraFrame() {
    var cameraFrameDiv = $('div.camera-frame')
    var cameraPlaceholder = cameraFrameDiv.find('div.camera-placeholder');
    var cameraProgress = cameraFrameDiv.find('div.camera-progress');
    var cameraImg = cameraFrameDiv.find('img.camera');
    var cameraId = cameraFrameDiv.attr('id').substring(6);
    var progressImg = cameraFrameDiv.find('img.camera-progress');
    var body = $('body');

    cameraFrameDiv[0].refreshDivider = 0;
    cameraFrameDiv[0].streamingFramerate = parseInt(cameraFrameDiv.attr('streaming_framerate')) || 1;
    cameraFrameDiv[0].streamingServerResize = cameraFrameDiv.attr('streaming_server_resize') == 'true';
    cameraFrameDiv[0].proto = cameraFrameDiv.attr('proto');
    cameraFrameDiv[0].url = cameraFrameDiv.attr('url');
    progressImg.attr('src', staticPath + 'img/camera-progress.gif');

    cameraProgress.addClass('visible');
    cameraPlaceholder.css('opacity', '0');

    /* fade in */
    cameraFrameDiv.animate({'opacity': 1}, 100);

    /* error and load handlers */
    cameraImg.on('error', function () {
        this.error = true;
        this.loading_count = 0;

        cameraImg.addClass('error').removeClass('loading');
        cameraPlaceholder.css('opacity', 1);
        cameraProgress.removeClass('visible');
        cameraFrameDiv.removeClass('motion-detected');
    });
    cameraImg.on('load', function () {
        if (refreshDisabled) {
            return; /* refresh temporarily disabled for updating */
        }

        this.error = false;
        this.loading_count = 0;

        cameraImg.removeClass('error').removeClass('loading');
        cameraPlaceholder.css('opacity', 0);
        cameraProgress.removeClass('visible');

        /* there's no point in looking for a cookie update more often than once every second */
        var now = new Date().getTime();
        if ((!this.lastCookieTime || now - this.lastCookieTime > 1000) && (cameraFrameDiv[0].proto != 'mjpeg')) {
            if (getCookie('motion_detected_' + cameraId) == 'true') {
                cameraFrameDiv.addClass('motion-detected');
            }
            else {
                cameraFrameDiv.removeClass('motion-detected');
            }

            this.lastCookieTime = now;
        }

        if (this.naturalWidth / this.naturalHeight > body.width() / body.height()) {
            cameraImg.css('width', '100%');
            cameraImg.css('height', 'auto');
        }
        else {
            cameraImg.css('width', 'auto');
            cameraImg.css('height', '100%');
        }
    });

    cameraImg.addClass('loading');
}

function refreshCameraFrame() {
    var $cameraFrame = $('div.camera-frame');
    var cameraFrame = $cameraFrame[0];
    var img = $cameraFrame.find('img.camera')[0];
    var cameraId = cameraFrame.id.substring(6);

    if (cameraFrame.proto == 'mjpeg') {
        /* no manual refresh for simple mjpeg cameras */
        var url = cameraFrame.url.replace('127.0.0.1', window.location.host.split(':')[0]);
        url += (url.indexOf('?') > 0 ? '&' : '?') + '_=' + new Date().getTime();
        img.src = url;
        return;
    }

    var count = 1000 / (refreshInterval * cameraFrame.streamingFramerate);

    if (img.error) {
        /* in case of error, decrease the refresh rate to 1 fps */
        count = 1000 / refreshInterval;
    }

    if (cameraFrame.refreshDivider < count) {
        cameraFrame.refreshDivider++;
    }
    else {
        (function () {
            if (refreshDisabled) {
                /* camera refreshing disabled, retry later */

                return;
            }

            if (img.loading_count) {
                img.loading_count++; /* increases each time the camera would refresh but is still loading */

                if (img.loading_count > 2 * 1000 / refreshInterval) { /* limits the retry at one every two seconds */
                    img.loading_count = 0;
                }
                else {
                    return; /* wait for the previous frame to finish loading */
                }
            }

            var timestamp = new Date().getTime();
            var path = basePath + 'picture/' + cameraId + '/current/?_=' + timestamp;
            if (cameraFrame.serverSideResize) {
                path += '&width=' + img.width;
            }

            path = addAuthParams('GET', path);
            img.src = path;
            img.loading_count = 1;

            cameraFrame.refreshDivider = 0;
        })();
    }

    setTimeout(refreshCameraFrame, refreshInterval);
}


    /* startup function */

$(document).ready(function () {
    setupCameraFrame();
    refreshCameraFrame();
});
