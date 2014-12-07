
var refreshDisabled = false;
var inProgress = false;
var refreshInterval = 50; /* milliseconds */


    /* utils */

function getCookie(name) {
    if (document.cookie.length <= 0) {
        return null;
    }

    var start = document.cookie.indexOf(name + '=');
    if (start == -1) {
        return null;
    }
     
    var start = start + name.length + 1;
    var end = document.cookie.indexOf(';', start);
    if (end == -1) {
        end = document.cookie.length;
    }
    
    return unescape(document.cookie.substring(start, end));
}

    
    /* progress */

function beginProgress() {
    if (inProgress) {
        return; /* already in progress */
    }

    inProgress = true;
    
    /* show the camera progress indicator */
    $('div.camera-progress').addClass('visible');
}

function endProgress() {
    if (!inProgress) {
        return; /* not in progress */
    }
    
    inProgress = false;
    
    /* hide the camera progress indicator */
    $('div.camera-progress').removeClass('visible');
}


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
    cameraFrameDiv[0].streamingServerResize = cameraFrameDiv.attr('streaming_server_resize') == 'True';
    progressImg.attr('src', staticUrl + 'img/camera-progress.gif');
    
    cameraProgress.addClass('visible');
    cameraPlaceholder.css('opacity', '0');
    
    /* fade in */
    cameraFrameDiv.animate({'opacity': 1}, 100);
    
    /* error and load handlers */
    cameraImg.error(function () {
        this.error = true;
        this.loading = 0;
        
        cameraImg.addClass('error').removeClass('loading');
        cameraPlaceholder.css('opacity', 1);
        cameraProgress.removeClass('visible');
        cameraFrameDiv.removeClass('motion-detected');
    });
    cameraImg.load(function () {
        if (refreshDisabled) {
            return; /* refresh temporarily disabled for updating */
        }
        
        this.error = false;
        this.loading = 0;
        
        cameraImg.removeClass('error').removeClass('loading');
        cameraPlaceholder.css('opacity', 0);
        cameraProgress.removeClass('visible');
        
        if (getCookie('motion_detected_' + cameraId) == 'true') {
            cameraFrameDiv.addClass('motion-detected');
        }
        else {
            cameraFrameDiv.removeClass('motion-detected');
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
    
    /* limit the refresh rate to 20 fps */
    var count = Math.max(1, 1 / cameraFrame.streamingFramerate * 1000 / refreshInterval);
    
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
            
            if (img.loading) {
                img.loading++; /* increases each time the camera would refresh but is still loading */
                
                if (img.loading > 2 * 1000 / refreshInterval) { /* limits the retry at one every two seconds */
                    img.loading = 0;
                }
                else {
                    return; /* wait for the previous frame to finish loading */
                }
            }
            
            var timestamp = Math.round(new Date().getTime());
            
            var uri = '/picture/' + cameraId + '/current/?seq=' + timestamp;
            if (cameraFrame.serverSideResize) {
                uri += '&width=' + img.width;
            }
            
            img.src = uri;
            img.loading = 1;
            
            cameraFrame.refreshDivider = 0;
        })();
    }

    setTimeout(refreshCameraFrame, refreshInterval);
}

function checkCameraErrors() {
    /* properly triggers the onerror event on the cameras whose imgs were not successfully loaded,
     * but the onerror event hasn't been triggered, for some reason (seems to happen in Chrome) */
    var cameraFrame = $('div.camera-frame').find('img.camera');
    
    cameraFrame.each(function () {
        if (this.complete === true && this.naturalWidth === 0 && !this.error && this.src) {
            $(this).error();
        }
    });
    
    setTimeout(checkCameraErrors, 500);
}


    /* startup function */

$(document).ready(function () {
    beginProgress();
    setupCameraFrame();
    refreshCameraFrame();
    checkCameraErrors();
});

