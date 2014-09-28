var pushConfigs = {};
var refreshDisabled = {}; /* dictionary indexed by cameraId, tells if refresh is disabled for a given camera */
var fullScreenCameraId = null;
var inProgress = false;
var refreshInterval = 50; /* milliseconds */


    /* utils */

function ajax(method, url, data, callback) {
    var options = {
        type: method,
        url: url,
        data: data,
        cache: false,
        success: callback,
        error: function (request, options, error) {
            showErrorMessage();
            if (callback) {
                callback();
            }
        }
    };
    
    if (data && method === 'POST' && typeof data === 'object') {
        options['contentType'] = 'application/json';
        options['data'] = JSON.stringify(options['data']);
    }
    
    $.ajax(options);
}

function showErrorMessage(message) {
    if (message == null || message == true) {
        message = 'An error occurred. Refreshing is recommended.';
    }
    
    showPopupMessage(message, 'error');
}

function doLogout() {
    /* IE is always a breed apart */
    if (window.ActiveXObject && document.execCommand) {
        if (document.execCommand('ClearAuthenticationCache')) {
            window.location.href = '/?logout=true';
        }
    }
    else {
        var username = ' ';
        var password = 'logout' + new Date().getTime();
    
        $.ajax({
            url: '/?logout=true',
            username: username,
            password: password,
            complete: function () {
                window.location.href = '/?logout=true';
            }
        });
    }
}

Object.keys = Object.keys || (function () {
    var hasOwnProperty = Object.prototype.hasOwnProperty;
    var hasDontEnumBug = !({toString: null}).propertyIsEnumerable('toString');
    var dontEnums = [
        'toString',
        'toLocaleString',
        'valueOf',
        'hasOwnProperty',
        'isPrototypeOf',
        'propertyIsEnumerable',
        'constructor'
    ];
    var dontEnumsLength = dontEnums.length;

    return function (obj) {
        if (typeof obj !== 'object' && typeof obj !== 'function' || obj === null) {
            return [];
        }

        var result = [];
        for (var prop in obj) {
            if (hasOwnProperty.call(obj, prop)) {
                result.push(prop);
            }
        }

        if (hasDontEnumBug) {
            for (var i = 0; i < dontEnumsLength; i++) {
                if (hasOwnProperty.call(obj, dontEnums[i])) {
                    result.push(dontEnums[i]);
                }
            }
        }
        
        return result;
    };
})();

Object.update = function (dest, source) {
    for (var key in source) {
        if (!source.hasOwnProperty(key)) {
            continue;
        }
        
        dest[key] = source[key];
    }
};

Array.prototype.indexOf = Array.prototype.indexOf || function (obj) {
    for (var i = 0; i < this.length; i++) {
        if (this[i] === obj) {
            return i;
        }
    }
    
    return -1;
};

Array.prototype.forEach = Array.prototype.forEach || function (callback, thisArg) {
    for (var i = 0; i < this.length; i++) {
        callback.call(thisArg, this[i], i, this);
    }
};

Array.prototype.unique = function (callback, thisArg) {
    var uniqueElements = [];
    this.forEach(function (element) {
        if (uniqueElements.indexOf(element, Utils.equals) === -1) {
            uniqueElements.push(element);
        }
    });
    
    return uniqueElements;
};

Array.prototype.filter = function (func, thisArg) {
    var filtered = [];
    for (var i = 0; i < this.length; i++) {
        if (func.call(thisArg, this[i], i, this)) {
            filtered.push(this[i]);
        }
    }
    
    return filtered;
};

Array.prototype.map = function (func, thisArg) {
    var mapped = [];
    for (var i = 0; i < this.length; i++) {
        mapped.push(func.call(thisArg, this[i], i, this));
    }
    
    return mapped;
};

Array.prototype.sortKey = function (keyFunc, reverse) {
    this.sort(function (e1, e2) {
        var k1 = keyFunc(e1);
        var k2 = keyFunc(e2);
        
        if ((k1 < k2 && !reverse) || (k1 > k2 && reverse)) {
            return -1;
        }
        else if ((k1 > k2 && !reverse) || (k1 < k2 && reverse)) {
            return 1;
        }
        else {
            return 0;
        }
    });
};

String.prototype.replaceAll = String.prototype.replaceAll || function (oldStr, newStr) {
    var p, s = this;
    while ((p = s.indexOf(oldStr)) >= 0) {
        s = s.substring(0, p) + newStr + s.substring(p + oldStr.length, s.length);
    }
    
    return s.toString();
};

function makeDeviceUrl(dict) {
    switch (dict.proto) {
        case 'v4l2':
            return dict.proto + '://' + dict.uri;
            
        case 'motioneye':
            return dict.proto + '://' + dict.host + (dict.port ? ':' + dict.port : '') + dict.uri + '/config/' + dict.remote_camera_id;
            
        default: /* assuming netcam */
            return dict.proto + '://' + dict.host + (dict.port ? ':' + dict.port : '') + dict.uri;
    }
}


    /* UI initialization */

function initUI() {
    /* checkboxes */
    $('input[type=checkbox].styled').each(function () {
        makeCheckBox($(this));
    });

    /* sliders */
    makeSlider($('#brightnessSlider'), 0, 100, 2, null, 5, 0, '%');
    makeSlider($('#contrastSlider'), 0, 100, 2, null, 5, 0, '%');
    makeSlider($('#saturationSlider'), 0, 100, 2, null, 5, 0, '%');
    makeSlider($('#hueSlider'), 0, 100, 2, null, 5, 0, '%');
    makeSlider($('#framerateSlider'), 2, 30, 0, [
        {value: 1, label: '1'},
        {value: 5, label: '5'},
        {value: 10, label: '10'},
        {value: 15, label: '15'},
        {value: 20, label: '20'},
        {value: 25, label: '25'},
        {value: 30, label: '30'}
    ], null, 0);
    makeSlider($('#streamingFramerateSlider'), 1, 30, 0, [
        {value: 1, label: '1'},
        {value: 5, label: '5'},
        {value: 10, label: '10'},
        {value: 15, label: '15'},
        {value: 20, label: '20'},
        {value: 25, label: '25'},
        {value: 30, label: '30'}
    ], null, 0);
    makeSlider($('#streamingQualitySlider'), 0, 100, 2, null, 5, 0, '%');
    makeSlider($('#streamingResolutionSlider'), 0, 100, 2, null, 5, 0, '%');
    makeSlider($('#imageQualitySlider'), 0, 100, 2, null, 5, 0, '%');
    makeSlider($('#movieQualitySlider'), 0, 100, 2, null, 5, 0, '%');
    makeSlider($('#frameChangeThresholdSlider'), 0, 10, 0, null, 6, 1, '%');
    
    makeSlider($('#noiseLevelSlider'), 0, 25, 0, null, 6, 0, '%');
    
    /* text validators */
    makeTextValidator($('#adminUsernameEntry'), true);
    makeTextValidator($('#normalUsernameEntry'), true);
    makeTextValidator($('#wifiNameEntry'), true);
    makeTextValidator($('#deviceNameEntry'), true);
    makeTextValidator($('#networkServerEntry'), true);
    makeTextValidator($('#networkShareNameEntry'), true);
    makeTextValidator($('#networkUsernameEntry'), false);
    makeTextValidator($('#networkPasswordEntry'), false);
    makeTextValidator($('#rootDirectoryEntry'), true);
    makeTextValidator($('#leftTextEntry'), true);
    makeTextValidator($('#rightTextEntry'), true);
    makeTextValidator($('#imageFileNameEntry'), true);
    makeTextValidator($('#movieFileNameEntry'), true);
    makeTextValidator($('#emailAddressesEntry'), true);
    makeTextValidator($('#smtpServerEntry'), true);
    makeTextValidator($('#smtpAccountEntry'), true);
    makeTextValidator($('#smtpPasswordEntry'), true);
    makeTextValidator($('#webHookUrlEntry'), true);
    makeTextValidator($('#commandNotificationsEntry'), true);
    
    /* number validators */
    makeNumberValidator($('#streamingPortEntry'), 1024, 65535, false, false, true);
    makeNumberValidator($('#snapshotIntervalEntry'), 1, 86400, false, false, true);
    makeNumberValidator($('#picturesLifetime'), 1, 3650, false, false, true);
    makeNumberValidator($('#moviesLifetime'), 1, 3650, false, false, true);
    makeNumberValidator($('#eventGapEntry'), 1, 86400, false, false, true);
    makeNumberValidator($('#preCaptureEntry'), 0, 100, false, false, true);
    makeNumberValidator($('#postCaptureEntry'), 0, 100, false, false, true);
    makeNumberValidator($('#smtpPortEntry'), 1, 65535, false, false, true);
    
    /* time validators */
    makeTimeValidator($('#mondayFromEntry'));
    makeTimeValidator($('#mondayToEntry'));
    makeTimeValidator($('#tuesdayFromEntry'));
    makeTimeValidator($('#tuesdayToEntry'));
    makeTimeValidator($('#wednesdayFromEntry'));
    makeTimeValidator($('#wednesdayToEntry'));
    makeTimeValidator($('#thursdayFromEntry'));
    makeTimeValidator($('#thursdayToEntry'));
    makeTimeValidator($('#fridayFromEntry'));
    makeTimeValidator($('#fridayToEntry'));
    makeTimeValidator($('#saturdayFromEntry'));
    makeTimeValidator($('#saturdayToEntry'));
    makeTimeValidator($('#sundayFromEntry'));
    makeTimeValidator($('#sundayToEntry'));
    
    /* ui elements that enable/disable other ui elements */
    $('#motionEyeSwitch').change(updateConfigUi);
    $('#showAdvancedSwitch').change(updateConfigUi);
    $('#wifiSwitch').change(updateConfigUi);
    $('#storageDeviceSelect').change(updateConfigUi);
    $('#resolutionSelect').change(updateConfigUi);
    $('#leftTextSelect').change(updateConfigUi);
    $('#rightTextSelect').change(updateConfigUi);
    $('#captureModeSelect').change(updateConfigUi);
    $('#autoNoiseDetectSwitch').change(updateConfigUi);
    $('#videoDeviceSwitch').change(updateConfigUi);
    $('#textOverlaySwitch').change(updateConfigUi);
    $('#videoStreamingSwitch').change(updateConfigUi);
    $('#streamingServerResizeSwitch').change(updateConfigUi);
    $('#stillImagesSwitch').change(updateConfigUi);
    $('#preservePicturesSelect').change(updateConfigUi);
    $('#motionDetectionSwitch').change(updateConfigUi);
    $('#motionMoviesSwitch').change(updateConfigUi);
    $('#preserveMoviesSelect').change(updateConfigUi);
    $('#emailNotificationsSwitch').change(updateConfigUi);
    $('#webHookNotificationsSwitch').change(updateConfigUi);
    $('#commandNotificationsSwitch').change(updateConfigUi);
    $('#workingScheduleSwitch').change(updateConfigUi);
    
    $('#mondayEnabledSwitch').change(updateConfigUi);
    $('#tuesdayEnabledSwitch').change(updateConfigUi);
    $('#wednesdayEnabledSwitch').change(updateConfigUi);
    $('#thursdayEnabledSwitch').change(updateConfigUi);
    $('#fridayEnabledSwitch').change(updateConfigUi);
    $('#saturdayEnabledSwitch').change(updateConfigUi);
    $('#sundayEnabledSwitch').change(updateConfigUi);
    
    $('#storageDeviceSelect').change(function () {
        $('#rootDirectoryEntry').val('/');
    });
    
    $('#rootDirectoryEntry').change(function () {
        if (this.value.charAt(0) !== '/') {
            this.value = '/' + this.value;
        }
    });
    
    /* fetch & push handlers */
    $('#cameraSelect').focus(function () {
        /* remember the previously selected index */
        this._prevSelectedIndex = this.selectedIndex;
    
    }).change(function () {
        if ($('#cameraSelect').val() === 'add') {
            runAddCameraDialog();
            this.selectedIndex = this._prevSelectedIndex;
        }
        else {
            this._prevSelectedIndex = this.selectedIndex;
            beginProgress([$(this).val()]);
            fetchCurrentCameraConfig(endProgress);
        }
    });
    $('input.general, select.general').change(pushMainConfig);
    $('input.wifi').change(pushMainConfig);
    $('input.device, select.device, ' +
      'input.storage, select.storage, ' +
      'input.text-overlay, select.text-overlay, ' + 
      'input.streaming, select.streaming, ' +
      'input.still-images, select.still-images, ' +
      'input.motion-detection, select.motion-detection, ' +
      'input.motion-movies, select.motion-movies, ' +
      'input.notifications, select.notifications, ' +
      'input.working-schedule, select.working-schedule').change(pushCameraConfig);
    
    /* preview controls */
    $('#brightnessSlider').change(function () {pushPreview('brightness');});
    $('#contrastSlider').change(function () {pushPreview('contrast');});
    $('#saturationSlider').change(function () {pushPreview('saturation');});
    $('#hueSlider').change(function () {pushPreview('hue');});
    
    /* apply button */
    $('#applyButton').click(function () {
        if ($(this).hasClass('progress')) {
            return; /* in progress */
        }
        
        doApply();
    });
    
    /* shut down button */
    $('#shutDownButton').click(function () {
        doShutDown();
    });
    
    /* whenever the window is resized,
     * if a modal dialog is visible, it should be repositioned */
    $(window).resize(updateModalDialogPosition);
    
    /* remove camera button */
    $('div.button.rem-camera-button').click(doRemCamera);
    
    /* logout button */
    $('div.button.logout-button').click(doLogout);
    
    /* read-only entries */
    $('#streamingSnapshotUrlEntry:text, #streamingMjpgUrlEntry:text, #streamingEmbedUrlEntry:text').click(function () {
        this.select();
    });
}


    /* settings */

function openSettings(cameraId) {
    if (cameraId != null) {
        $('#cameraSelect').val(cameraId).change();
    }
    
    $('div.settings').addClass('open').removeClass('closed');
    $('div.page-container').addClass('stretched');
    $('div.settings-top-bar').addClass('open').removeClass('closed');
    
    updateConfigUi();
}

function closeSettings() {
    hideApply();
    pushConfigs = {};
    
    $('div.settings').removeClass('open').addClass('closed');
    $('div.page-container').removeClass('stretched');
    $('div.settings-top-bar').removeClass('open').addClass('closed');
}

function isSettingsOpen() {
    return $('div.settings').hasClass('open');   
}

function updateConfigUi() {
    var objs = $('tr.settings-item, div.advanced-setting, table.advanced-setting, div.settings-section-title, table.settings');
    
    function markHide() {
        this._hide = true;
    }
    
    function unmarkHide() {
        this._hide = false;
    }
    
    objs.each(unmarkHide);
    
    /* sliders */
    $('input.range').each(function () {
        if  (this.value === '' || this.value == null) {
            $(this).parents('tr:eq(0)').each(markHide);
        }
    });
    
    /* general enable switch */
    var motionEyeEnabled = $('#motionEyeSwitch').get(0).checked;
    if (!motionEyeEnabled) {
        objs.not($('#motionEyeSwitch').parents('div').get(0)).each(markHide);
    }
    
    /* wifi switch */
    if (!$('#wifiSwitch').get(0).checked) {
        $('#wifiSwitch').parent().next('table.settings').find('tr.settings-item').each(markHide);
    }
    
    if ($('#cameraSelect').find('option').length < 2) { /* no camera configured */
        $('#videoDeviceSwitch').parent().each(markHide);
        $('#videoDeviceSwitch').parent().nextAll('div.settings-section-title, table.settings').each(markHide);
    }
    
    if ($('#videoDeviceSwitch')[0].error) { /* config error */
        $('#videoDeviceSwitch').parent().nextAll('div.settings-section-title, table.settings').each(markHide);
    }
        
    /* advanced settings */
    var showAdvanced = $('#showAdvancedSwitch').get(0).checked;
    if (!showAdvanced) {
        $('tr.advanced-setting, div.advanced-setting, table.advanced-setting').each(markHide);
    }
    
    /* video device */
    if ($('#brightnessSlider').val() == '') {
        $('#brightnessSlider').parents('tr:eq(0)').each(markHide);
    }
    if ($('#contrastSlider').val() == '') {
        $('#contrastSlider').parents('tr:eq(0)').each(markHide);
    }
    if ($('#saturationSlider').val() == '') {
        $('#saturationSlider').parents('tr:eq(0)').each(markHide);
    }
    if ($('#hueSlider').val() == '') {
        $('#hueSlider').parents('tr:eq(0)').each(markHide);
    }
    if ($('#contrastSlider').val() == '') {
        $('#contrastSlider').parents('tr:eq(0)').each(markHide);
    }
    if ($('#resolutionSelect')[0].selectedIndex == -1) {
        $('#resolutionSelect').parents('tr:eq(0)').each(markHide);
    }

    /* storage device */
    if ($('#storageDeviceSelect').val() !== 'network-share') {
        $('#networkServerEntry').parents('tr:eq(0)').each(markHide);
        $('#networkUsernameEntry').parents('tr:eq(0)').each(markHide);
        $('#networkPasswordEntry').parents('tr:eq(0)').each(markHide);
        $('#networkShareNameEntry').parents('tr:eq(0)').each(markHide);
    }
    
    /* text */
    if ($('#leftTextSelect').val() !== 'custom-text') {
        $('#leftTextEntry').parents('tr:eq(0)').each(markHide);
    }
    if ($('#rightTextSelect').val() !== 'custom-text') {
        $('#rightTextEntry').parents('tr:eq(0)').each(markHide);
    }
    
    /* still images capture mode */
    if ($('#captureModeSelect').val() !== 'interval-snapshots') {
        $('#snapshotIntervalEntry').parents('tr:eq(0)').each(markHide);
    }
    
    /* auto noise level */
    if ($('#autoNoiseDetectSwitch').get(0).checked) {
        $('#noiseLevelSlider').parents('tr:eq(0)').each(markHide);
    }
    
    /* video device switch */
    if (!$('#videoDeviceSwitch').get(0).checked) {
        $('#videoDeviceSwitch').parent().nextAll('div.settings-section-title, table.settings').each(markHide);
    }
    
    /* text overlay switch */
    if (!$('#textOverlaySwitch').get(0).checked) {
        $('#textOverlaySwitch').parent().next('table.settings').find('tr.settings-item').each(markHide);
    }
    
    /* video streaming */
    if (!$('#videoStreamingSwitch').get(0).checked) {
        $('#videoStreamingSwitch').parent().next('table.settings').find('tr.settings-item').not('.local-streaming').each(markHide);
    }
    if (!$('#streamingSnapshotUrlEntry').val()) {
        $('#streamingSnapshotUrlEntry').parents('tr:eq(0)').each(markHide);
    }
    if (!$('#streamingMjpgUrlEntry').val()) {
        $('#streamingMjpgUrlEntry').parents('tr:eq(0)').each(markHide);
    }
    if (!$('#streamingEmbedUrlEntry').val()) {
        $('#streamingEmbedUrlEntry').parents('tr:eq(0)').each(markHide);
    }
    if (!$('#streamingServerResizeSwitch').get(0).checked) {
        $('#streamingResolutionSlider').parents('tr:eq(0)').each(markHide);
    }
    
    /* still images switch */
    if (!$('#stillImagesSwitch').get(0).checked) {
        $('#stillImagesSwitch').parent().next('table.settings').find('tr.settings-item').each(markHide);
    }
    
    /* preserve pictures */
    if ($('#preservePicturesSelect').val() != '-1') {
        $('#picturesLifetime').parents('tr:eq(0)').each(markHide);
    }
    
    /* motion detection switch */
    if (!$('#motionDetectionSwitch').get(0).checked) {
        $('#motionDetectionSwitch').parent().next('table.settings').find('tr.settings-item').each(markHide);
        $('#motionMoviesSwitch').parent().each(markHide);
        $('#motionMoviesSwitch').parent().next('table.settings').each(markHide);
        $('#emailNotificationsSwitch').parents('table.settings:eq(0)').each(markHide);
        $('#emailNotificationsSwitch').parents('table.settings:eq(0)').prev().each(markHide);
        $('#workingScheduleSwitch').parent().each(markHide);
        $('#workingScheduleSwitch').parent().next('table.settings').each(markHide);
    }
    
    /* motion movies switch */
    if (!$('#motionMoviesSwitch').get(0).checked) {
        $('#motionMoviesSwitch').parent().next('table.settings').find('tr.settings-item').each(markHide);
    }
    
    /* preserve movies */
    if ($('#preserveMoviesSelect').val() != '-1') {
        $('#moviesLifetime').parents('tr:eq(0)').each(markHide);
    }
    
    /* event notifications */
    if (!$('#emailNotificationsSwitch').get(0).checked) {
        $('#emailAddressesEntry').parents('tr:eq(0)').each(markHide);
        $('#smtpServerEntry').parents('tr:eq(0)').each(markHide);
        $('#smtpPortEntry').parents('tr:eq(0)').each(markHide);
        $('#smtpAccountEntry').parents('tr:eq(0)').each(markHide);
        $('#smtpPasswordEntry').parents('tr:eq(0)').each(markHide);
        $('#smtpTlsSwitch').parents('tr:eq(0)').each(markHide);
    }
    
    if (!$('#webHookNotificationsSwitch').get(0).checked) {
        $('#webHookUrlEntry').parents('tr:eq(0)').each(markHide);
        $('#webHookHttpMethodSelect').parents('tr:eq(0)').each(markHide);
    }

    if (!$('#commandNotificationsSwitch').get(0).checked) {
        $('#commandNotificationsEntry').parents('tr:eq(0)').each(markHide);
    }

    /* working schedule */
    if (!$('#workingScheduleSwitch').get(0).checked) {
        $('#workingScheduleSwitch').parent().next('table.settings').find('tr.settings-item').each(markHide);
    }
    
    var weekDays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'];
    weekDays.forEach(function (weekDay) {
        var check = $('#' + weekDay + 'EnabledSwitch');
        if (check.get(0).checked) {
            check.parent().find('.time').show();
        }
        else {
            check.parent().find('.time').hide();
        }
    });
    
    objs.each(function () {
        if (this._hide) {
            $(this).hide(200);
        }
        else {
            $(this).show(200);
        }
    });
    
    /* re-validate all the validators */
    $('div.settings').find('.validator').each(function () {
        this.validate();
    });
    
    /* update all checkboxes and sliders */
    $('div.settings').find('input[type=checkbox], input.range').each(function () {
        this.update();
    });
    
    /* select the first option for the selects with no current selection */
    $('div.settings').find('select').not('#cameraSelect').each(function () {
        if (this.selectedIndex === -1) {
            this.selectedIndex = 0;
        }
    });
}

function configUiValid() {
    /* re-validate all the validators */
    $('div.settings').find('.validator').each(function () {
        this.validate();
    });
    
    var valid = true;
    $('div.settings input, select').each(function () {
        if (this.invalid) {
            valid = false;
            return false;
        }
    });
    
    return valid;
}

function mainUi2Dict() {
    return {
        'enabled': $('#motionEyeSwitch')[0].checked,
        
        'show_advanced': $('#showAdvancedSwitch')[0].checked,
        'admin_username': $('#adminUsernameEntry').val(),
        'admin_password': $('#adminPasswordEntry').val(),
        'normal_username': $('#normalUsernameEntry').val(),
        'normal_password': $('#normalPasswordEntry').val(),
        'time_zone': $('#timeZoneSelect').val(),
        
        'wifi_enabled': $('#wifiSwitch')[0].checked,
        'wifi_name': $('#wifiNameEntry').val(),
        'wifi_key': $('#wifiKeyEntry').val()
    };
}

function dict2MainUi(dict) {
    $('#motionEyeSwitch')[0].checked = dict['enabled'];
    
    $('#showAdvancedSwitch')[0].checked = dict['show_advanced'];
    $('#adminUsernameEntry').val(dict['admin_username']);
    $('#adminPasswordEntry').val(dict['admin_password']);
    $('#normalUsernameEntry').val(dict['normal_username']);
    $('#normalPasswordEntry').val(dict['normal_password']);
    $('#timeZoneSelect').val(dict['time_zone']);
    
    $('#wifiSwitch')[0].checked = dict['wifi_enabled'];
    $('#wifiNameEntry').val(dict['wifi_name']);
    $('#wifiKeyEntry').val(dict['wifi_key']);
    
    updateConfigUi();
}

function cameraUi2Dict() {
    if ($('#videoDeviceSwitch')[0].error) { /* config error */
        return {
            'enabled': $('#videoDeviceSwitch')[0].checked,
        };
    }
    
    var dict = {
        /* video device */
        'enabled': $('#videoDeviceSwitch')[0].checked,
        'name': $('#deviceNameEntry').val(),
        'light_switch_detect': $('#lightSwitchDetectSwitch')[0].checked,
        'rotation': $('#rotationSelect').val(),
        'framerate': $('#framerateSlider').val(),
        'proto': $('#deviceEntry')[0].proto,
        'host': $('#deviceEntry')[0].host,
        'port': $('#deviceEntry')[0].port,
        'uri': $('#deviceEntry')[0].uri,
        'username': $('#deviceEntry')[0].username,
        'password': $('#deviceEntry')[0].password,
        
        /* file storage */
        'storage_device': $('#storageDeviceSelect').val(),
        'network_server': $('#networkServerEntry').val(),
        'network_share_name': $('#networkShareNameEntry').val(),
        'network_username': $('#networkUsernameEntry').val(),
        'network_password': $('#networkPasswordEntry').val(),
        'root_directory': $('#rootDirectoryEntry').val(),
        
        /* text overlay */
        'text_overlay': $('#textOverlaySwitch')[0].checked,
        'left_text': $('#leftTextSelect').val(),
        'custom_left_text': $('#leftTextEntry').val(),
        'right_text': $('#rightTextSelect').val(),
        'custom_right_text': $('#rightTextEntry').val(),
        
        /* video streaming */
        'video_streaming': $('#videoStreamingSwitch')[0].checked,
        'streaming_framerate': $('#streamingFramerateSlider').val(),
        'streaming_quality': $('#streamingQualitySlider').val(),
        'streaming_resolution': $('#streamingResolutionSlider').val(),
        'streaming_server_resize': $('#streamingServerResizeSwitch')[0].checked,
        'streaming_port': $('#streamingPortEntry').val(),
        'streaming_motion': $('#streamingMotion')[0].checked,
        
        /* still images */
        'still_images': $('#stillImagesSwitch')[0].checked,
        'image_file_name': $('#imageFileNameEntry').val(),
        'image_quality': $('#imageQualitySlider').val(),
        'capture_mode': $('#captureModeSelect').val(),
        'snapshot_interval': $('#snapshotIntervalEntry').val(),
        'preserve_pictures': $('#preservePicturesSelect').val() >= 0 ? $('#preservePicturesSelect').val() : $('#picturesLifetime').val(),
        
        /* motion detection */
        'motion_detection': $('#motionDetectionSwitch')[0].checked,
        'show_frame_changes': $('#showFrameChangesSwitch')[0].checked,
        'frame_change_threshold': $('#frameChangeThresholdSlider').val(),
        'auto_noise_detect': $('#autoNoiseDetectSwitch')[0].checked,
        'noise_level': $('#noiseLevelSlider').val(),
        'event_gap': $('#eventGapEntry').val(),
        'pre_capture': $('#preCaptureEntry').val(),
        'post_capture': $('#postCaptureEntry').val(),
        
        /* motion movies */
        'motion_movies': $('#motionMoviesSwitch')[0].checked,
        'movie_file_name': $('#movieFileNameEntry').val(),
        'movie_quality': $('#movieQualitySlider').val(),
        'preserve_movies': $('#preserveMoviesSelect').val() >= 0 ? $('#preserveMoviesSelect').val() : $('#moviesLifetime').val(),
        
        /* motion notifications */
        'email_notifications_enabled': $('#emailNotificationsSwitch')[0].checked,
        'email_notifications_addresses': $('#emailAddressesEntry').val(),
        'email_notifications_smtp_server': $('#smtpServerEntry').val(),
        'email_notifications_smtp_port': $('#smtpPortEntry').val(),
        'email_notifications_smtp_account': $('#smtpAccountEntry').val(),
        'email_notifications_smtp_password': $('#smtpPasswordEntry').val(),
        'email_notifications_smtp_tls': $('#smtpTlsSwitch')[0].checked,
        'web_hook_notifications_enabled': $('#webHookNotificationsSwitch')[0].checked,
        'web_hook_notifications_url': $('#webHookUrlEntry').val(),
        'web_hook_notifications_http_method': $('#webHookHttpMethodSelect').val(),
        'command_notifications_enabled': $('#commandNotificationsSwitch')[0].checked,
        'command_notifications_exec': $('#commandNotificationsEntry').val(),
        
        /* working schedule */
        'working_schedule': $('#workingScheduleSwitch')[0].checked,
        'monday_from': $('#mondayEnabledSwitch')[0].checked ? $('#mondayFromEntry').val() : '',
        'monday_to':$('#mondayEnabledSwitch')[0].checked ? $('#mondayToEntry').val() : '',
        'tuesday_from': $('#tuesdayEnabledSwitch')[0].checked ? $('#tuesdayFromEntry').val() : '',
        'tuesday_to': $('#tuesdayEnabledSwitch')[0].checked ? $('#tuesdayToEntry').val() : '',
        'wednesday_from': $('#wednesdayEnabledSwitch')[0].checked ? $('#wednesdayFromEntry').val() : '',
        'wednesday_to': $('#wednesdayEnabledSwitch')[0].checked ? $('#wednesdayToEntry').val() : '',
        'thursday_from': $('#thursdayEnabledSwitch')[0].checked ? $('#thursdayFromEntry').val() : '',
        'thursday_to': $('#thursdayEnabledSwitch')[0].checked ? $('#thursdayToEntry').val() : '',
        'friday_from': $('#fridayEnabledSwitch')[0].checked ? $('#fridayFromEntry').val() : '',
        'friday_to': $('#fridayEnabledSwitch')[0].checked ? $('#fridayToEntry').val() :'',
        'saturday_from': $('#saturdayEnabledSwitch')[0].checked ? $('#saturdayFromEntry').val() : '',
        'saturday_to': $('#saturdayEnabledSwitch')[0].checked ? $('#saturdayToEntry').val() : '',
        'sunday_from': $('#sundayEnabledSwitch')[0].checked ? $('#sundayFromEntry').val() : '',
        'sunday_to': $('#sundayEnabledSwitch')[0].checked ? $('#sundayToEntry').val() : '',
        'working_schedule_type': $('#workingScheduleTypeSelect').val(),
    };

    if ($('#resolutionSelect')[0].selectedIndex != -1) {
        dict.resolution = $('#resolutionSelect').val();
    }

    if ($('#brightnessSlider').val() !== '') {
        dict.brightness = $('#brightnessSlider').val();
    }

    if ($('#contrastSlider').val() !== '') {
        dict.contrast = $('#contrastSlider').val();
    }
    
    if ($('#saturationSlider').val() !== '') {
        dict.saturation = $('#saturationSlider').val();
    }
    
    if ($('#hueSlider').val() !== '') {
        dict.hue = $('#hueSlider').val();
    }
    
    return dict;
}

function dict2CameraUi(dict) {
    if (dict == null) {
        /* errors while getting the configuration */
        
        $('#videoDeviceSwitch')[0].error = true;
        $('#videoDeviceSwitch')[0].checked = false;
        updateConfigUi();
        
        return;
    }
    else {
        $('#videoDeviceSwitch')[0].error = false;
    }
    
    /* video device */
    $('#videoDeviceSwitch')[0].checked = dict['enabled'];
    $('#deviceNameEntry').val(dict['name']);
    $('#deviceEntry').val(makeDeviceUrl(dict));
    $('#deviceEntry')[0].proto = dict['proto'];
    $('#deviceEntry')[0].host = dict['host'];
    $('#deviceEntry')[0].port = dict['port'];
    $('#deviceEntry')[0].uri= dict['uri'];
    $('#deviceEntry')[0].username = dict['username'];
    $('#deviceEntry')[0].password = dict['password'];
    $('#lightSwitchDetectSwitch')[0].checked = dict['light_switch_detect'];
    
    if (dict['brightness'] != null) {
        $('#brightnessSlider').val(dict['brightness']);
    }
    else {
        $('#brightnessSlider').val('');
    }
    
    if (dict['contrast'] != null) {
        $('#contrastSlider').val(dict['contrast']);
    }
    else {
        $('#contrastSlider').val('');
    }
    
    if (dict['saturation'] != null) {
        $('#saturationSlider').val(dict['saturation']);
    }
    else {
        $('#saturationSlider').val('');
    }
    
    if (dict['hue'] != null) {
        $('#hueSlider').val(dict['hue']);
    }
    else {
        $('#hueSlider').val('');
    }

    $('#resolutionSelect').html('');
    if (dict['available_resolutions']) {
        dict['available_resolutions'].forEach(function (resolution) {
            $('#resolutionSelect').append('<option value="' + resolution + '">' + resolution + '</option>');
        });
    }
    $('#resolutionSelect').val(dict['resolution']);
    
    $('#rotationSelect').val(dict['rotation']);
    $('#framerateSlider').val(dict['framerate']);
    
    /* file storage */
    $('#storageDeviceSelect').empty();
    dict['available_disks'] = dict['available_disks'] || [];
    var storageDeviceOptions = {'network-share': true};
    dict['available_disks'].forEach(function (disk) {
        disk.partitions.forEach(function (partition) {
            var target = partition.target.replaceAll('/', '-');
            var option = 'local-disk' + target;
            var label = partition.vendor;
            if (partition.model) {
                label += ' ' + partition.model;
            }
            if (disk.partitions.length > 1) {
                label += '/part' + partition.part_no;
            }
            label += ' (' + partition.target + ')';
            
            storageDeviceOptions[option] = true;
            
            $('#storageDeviceSelect').append('<option value="' + option + '">' + label + '</option>');
        });
    });
    $('#storageDeviceSelect').append('<option value="custom-path">Custom Path</option>');
    if (dict['smb_shares']) {
        $('#storageDeviceSelect').append('<option value="network-share">Network Share</option>');
    }

    if (storageDeviceOptions[dict['storage_device']]) {
        $('#storageDeviceSelect').val(dict['storage_device']);
    }
    else {
        $('#storageDeviceSelect').val('custom-path');
    }
    $('#networkServerEntry').val(dict['network_server']);
    $('#networkShareNameEntry').val(dict['network_share_name']);
    $('#networkUsernameEntry').val(dict['network_username']);
    $('#networkPasswordEntry').val(dict['network_password']);
    $('#rootDirectoryEntry').val(dict['root_directory']);
    var percent = 0;
    if (dict['disk_total'] != 0) {
        percent = parseInt(dict['disk_used'] * 100 / dict['disk_total']);
    }
    $('#diskUsageBarFill').css('width', percent + '%');
    $('#diskUsageText').html(
            (dict['disk_used'] / 1073741824).toFixed(1)  + '/' + (dict['disk_total'] / 1073741824).toFixed(1) + ' GB (' + percent + '%)');
    
    /* text overlay */
    $('#textOverlaySwitch')[0].checked = dict['text_overlay'];
    $('#leftTextSelect').val(dict['left_text']);
    $('#leftTextEntry').val(dict['custom_left_text']);
    $('#rightTextSelect').val(dict['right_text']);
    $('#rightTextEntry').val(dict['custom_right_text']);
    
    /* video streaming */
    $('#videoStreamingSwitch')[0].checked = dict['video_streaming'];
    $('#streamingFramerateSlider').val(dict['streaming_framerate']);
    $('#streamingQualitySlider').val(dict['streaming_quality']);
    $('#streamingResolutionSlider').val(dict['streaming_resolution']);
    $('#streamingServerResizeSwitch')[0].checked = dict['streaming_server_resize'];
    $('#streamingPortEntry').val(dict['streaming_port']);
    $('#streamingMotion')[0].checked = dict['streaming_motion'];
    
    var cameraUrl = location.protocol + '//' + location.host + '/picture/' + dict.id + '/';
    $('#streamingSnapshotUrlEntry').val(cameraUrl + 'current/');
    if (dict.proto == 'motioneye') {
        $('#streamingMjpgUrlEntry').val('');
    }
    else {
        $('#streamingMjpgUrlEntry').val(location.protocol + '//' + location.host.split(':')[0] + ':' + dict.streaming_port);
    }
    $('#streamingEmbedUrlEntry').val(cameraUrl + 'frame/');
    
    /* still images */
    $('#stillImagesSwitch')[0].checked = dict['still_images'];
    $('#imageFileNameEntry').val(dict['image_file_name']);
    $('#imageQualitySlider').val(dict['image_quality']);
    $('#captureModeSelect').val(dict['capture_mode']);
    $('#snapshotIntervalEntry').val(dict['snapshot_interval']);
    $('#preservePicturesSelect').val(dict['preserve_pictures']);
    if ($('#preservePicturesSelect').val() == null) {
        $('#preservePicturesSelect').val('-1');
    }
    $('#picturesLifetime').val(dict['preserve_pictures']);
    
    /* motion detection */
    $('#motionDetectionSwitch')[0].checked = dict['motion_detection'];
    $('#showFrameChangesSwitch')[0].checked = dict['show_frame_changes'];
    $('#frameChangeThresholdSlider').val(dict['frame_change_threshold']);
    $('#autoNoiseDetectSwitch')[0].checked = dict['auto_noise_detect'];
    $('#noiseLevelSlider').val(dict['noise_level']);
    $('#eventGapEntry').val(dict['event_gap']);
    $('#preCaptureEntry').val(dict['pre_capture']);
    $('#postCaptureEntry').val(dict['post_capture']);
    
    /* motion movies */
    $('#motionMoviesSwitch')[0].checked = dict['motion_movies'];
    $('#movieFileNameEntry').val(dict['movie_file_name']);
    $('#movieQualitySlider').val(dict['movie_quality']);
    $('#preserveMoviesSelect').val(dict['preserve_movies']);
    if ($('#preserveMoviesSelect').val() == null) {
        $('#preserveMoviesSelect').val('-1');
    }
    $('#moviesLifetime').val(dict['preserve_movies']);
    
    /* motion notifications */
    $('#emailNotificationsSwitch')[0].checked = dict['email_notifications_enabled'];
    $('#emailAddressesEntry').val(dict['email_notifications_addresses']);
    $('#smtpServerEntry').val(dict['email_notifications_smtp_server']);
    $('#smtpPortEntry').val(dict['email_notifications_smtp_port']);
    $('#smtpAccountEntry').val(dict['email_notifications_smtp_account']);
    $('#smtpPasswordEntry').val(dict['email_notifications_smtp_password']);
    $('#smtpTlsSwitch')[0].checked = dict['email_notifications_smtp_tls'];
    $('#webHookNotificationsSwitch')[0].checked = dict['web_hook_notifications_enabled'];
    $('#webHookUrlEntry').val(dict['web_hook_notifications_url']);
    $('#webHookHttpMethodSelect').val(dict['web_hook_notifications_http_method']);
    $('#commandNotificationsSwitch')[0].checked = dict['command_notifications_enabled'];
    $('#commandNotificationsEntry').val(dict['command_notifications_exec']);

    /* working schedule */
    $('#workingScheduleSwitch')[0].checked = dict['working_schedule'];
    $('#mondayEnabledSwitch')[0].checked = Boolean(dict['monday_from'] && dict['monday_to']);
    $('#mondayFromEntry').val(dict['monday_from']);
    $('#mondayToEntry').val(dict['monday_to']);
    $('#tuesdayEnabledSwitch')[0].checked = Boolean(dict['tuesday_from'] && dict['tuesday_to']);
    $('#tuesdayFromEntry').val(dict['tuesday_from']);
    $('#tuesdayToEntry').val(dict['tuesday_to']);
    $('#wednesdayEnabledSwitch')[0].checked = Boolean(dict['wednesday_from'] && dict['wednesday_to']);
    $('#wednesdayFromEntry').val(dict['wednesday_from']);
    $('#wednesdayToEntry').val(dict['wednesday_to']);
    $('#thursdayEnabledSwitch')[0].checked = Boolean(dict['thursday_from'] && dict['thursday_to']);
    $('#thursdayFromEntry').val(dict['thursday_from']);
    $('#thursdayToEntry').val(dict['thursday_to']);
    $('#fridayEnabledSwitch')[0].checked = Boolean(dict['friday_from'] && dict['friday_to']);
    $('#fridayFromEntry').val(dict['friday_from']);
    $('#fridayToEntry').val(dict['friday_to']);
    $('#saturdayEnabledSwitch')[0].checked = Boolean(dict['saturday_from'] && dict['saturday_to']);
    $('#saturdayFromEntry').val(dict['saturday_from']);
    $('#saturdayToEntry').val(dict['saturday_to']);
    $('#sundayEnabledSwitch')[0].checked = Boolean(dict['sunday_from'] && dict['sunday_to']);
    $('#sundayFromEntry').val(dict['sunday_from']);
    $('#sundayToEntry').val(dict['sunday_to']);
    $('#workingScheduleTypeSelect').val(dict['working_schedule_type']);
    
    updateConfigUi();
}

    
    /* progress */

function beginProgress(cameraIds) {
    if (inProgress) {
        return; /* already in progress */
    }

    inProgress = true;
    
    /* replace the main page message with a progress indicator */
    $('div.add-camera-message').html('<img class="main-loading-progress" src="' + staticUrl + 'img/main-loading-progress.gif">');
    
    /* show the apply button progress indicator */
    $('#applyButton').html('<img class="apply-progress" src="' + staticUrl + 'img/apply-progress.gif">');
    
    /* show the camera progress indicators */
    if (cameraIds) {
        cameraIds.forEach(function (cameraId) {
            $('div.camera-frame#camera' + cameraId + ' div.camera-progress').addClass('visible');
        });
    }
    else {
        $('div.camera-progress').addClass('visible');
    }
    
    /* remove the settings progress lock */
    $('div.settings-progress').css('width', '100%').css('opacity', '0.9');
}

function endProgress() {
    if (!inProgress) {
        return; /* not in progress */
    }
    
    inProgress = false;
    
    /* remove any existing message on the main page */
    $('div.add-camera-message').remove();
    
    /* deal with the apply button */
    if (Object.keys(pushConfigs).length === 0) {
        hideApply();
    }
    else {
        showApply();
    }
    
    /* hide the settings progress lock */
    $('div.settings-progress').css('opacity', '0');
    
    /* hide the camera progress indicator */
    $('div.camera-progress').removeClass('visible');

    setTimeout(function () {
        $('div.settings-progress').css('width', '0px');
    }, 500);
}

function downloadFile(uri) {
    var url = window.location.href;
    var parts = url.split('/');
    url = parts.slice(0, 3).join('/') + uri;
    
    /* download the file by creating a temporary iframe */
    var frame = $('<iframe style="display: none;"></iframe>');
    frame.attr('src', url);
    $('body').append(frame);
}


    /* apply button */

function showApply() {
    var applyButton = $('#applyButton');
    
    applyButton.html('Apply');
    applyButton.css('display', 'inline-block');
    applyButton.removeClass('progress');
    setTimeout(function () {
        applyButton.css('opacity', '1');
    }, 10);
}

function hideApply() {
    var applyButton = $('#applyButton');
    
    applyButton.css('opacity', '0');
    applyButton.removeClass('progress');
    
    setTimeout(function () {
        applyButton.css('display', 'none');
    }, 500);
}

function isApplyVisible() {
    var applyButton = $('#applyButton');
    
    return applyButton.is(':visible');
}

function doApply() {
    if (!configUiValid()) {
        runAlertDialog('Make sure all the configuration options are valid!');
        
        return;
    }
    
    /* gather the affected motion instances */
    var affectedInstances = {};
    Object.keys(pushConfigs).forEach(function (key) {
        var config = pushConfigs[key];
        if (key === 'main') {
            return;
        }
        
        var instance;
        if (config.proto == 'http' || config.proto == 'v4l2') {
            instance = '';
        }
        else { /* motioneye */
            instance = config.host || '';
            if (config.port) {
                instance += ':' + config.port;
            }
        }
        
        affectedInstances[instance] = true;
    });
    affectedInstances = Object.keys(affectedInstances);
    
    /* compute the affected camera ids */ 
    var cameraIdsByInstance = getCameraIdsByInstance();
    var affectedCameraIds = [];
    
    affectedInstances.forEach(function (instance) {
        affectedCameraIds = affectedCameraIds.concat(cameraIdsByInstance[instance] || []);
    });
    
    beginProgress(affectedCameraIds);
    affectedCameraIds.forEach(function (cameraId) {
        refreshDisabled[cameraId] |= 0;
        refreshDisabled[cameraId]++;
    });
    
    ajax('POST', '/config/0/set/', pushConfigs, function (data) {
        affectedCameraIds.forEach(function (cameraId) {
            refreshDisabled[cameraId]--;
        });
        
        if (data == null || data.error) {
            endProgress();
            showErrorMessage(data && data.error);
            return;
        }
        
        if (data.reboot) {
            var count = 0;
            function checkServerReboot() {
                $.ajax({
                    type: 'GET',
                    url: '/config/0/get/',
                    success: function () {
                        window.location.reload(true);
                    },
                    error: function () {
                        if (count < 25) {
                            count += 1;
                            setTimeout(checkServerReboot, 2000);
                        }
                        else {
                            window.location.reload(true);
                        }
                    }
                });
            }
            
            setTimeout(checkServerReboot, 15000);
            
            return;
        }
        
        if (data.reload) {
            window.location.reload(true);
            return;
        }
        
        /* update the camera name in the device select
         * and frame title bar */
        Object.keys(pushConfigs).forEach(function (key) {
            var config = pushConfigs[key];
            if (config.key !== 'main') {
                $('#cameraSelect').find('option[value=' + key + ']').html(config.name);
            }
            
            $('#camera' + key).find('span.camera-name').html(config.name);
        });

        pushConfigs = {};
        endProgress();
        recreateCameraFrames(); /* a camera could have been disabled */
    });
}

function doShutDown() {
    runConfirmDialog('Really shut down?', function () {
        ajax('POST', '/power/shutdown/');    
    });
}

function doRemCamera() {
    if (Object.keys(pushConfigs).length) {
        return runAlertDialog('Please apply the modified settings first!');
    }
    
    var cameraId = $('#cameraSelect').val();
    if (cameraId == null || cameraId === 'add') {
        runAlertDialog('No camera to remove!');
        return;
    }

    var deviceName = $('#cameraSelect').find('option[value=' + cameraId + ']').text();
    
    runConfirmDialog('Remove camera ' + deviceName + '?', function () {
        /* disable further refreshing of this camera */
        var img = $('div.camera-frame#camera' + cameraId).find('img.camera');
        if (img.length) {
            img[0].loading = 1;
        }

        beginProgress();
        ajax('POST', '/config/' + cameraId + '/rem/', null, function (data) {
            if (data == null || data.error) {
                endProgress();
                showErrorMessage(data && data.error);
                return;
            }
            
            fetchCurrentConfig(endProgress);
        });
    });
}

function doUpdate() {
    if (Object.keys(pushConfigs).length) {
        return runAlertDialog('Please apply the modified settings first!');
    }
    
    showModalDialog('<div class="modal-progress"></div>');
    ajax('GET', '/update/', null, function (data) {
        if (data.update_version == null) {
            runAlertDialog('motionEye is up to date (current version: ' + data.current_version + ')');
        }
        else {
            runConfirmDialog('New version available: ' + data.update_version + '. Update?', function () {
                showModalDialog('<div style="text-align: center;"><span>This may take a few minutes.</span><div class="modal-progress"></div></div>');
                ajax('POST', '/update/?version=' + data.update_version, null, function () {
                    var count = 0;
                    function checkServerUpdate() {
                        $.ajax({
                            type: 'GET',
                            url: '/config/0/get/',
                            success: function () {
                                runAlertDialog('motionEye was successfully updated!', function () {
                                    window.location.reload(true);
                                });
                            },
                            error: function () {
                                if (count < 25) {
                                    count += 1;
                                    setTimeout(checkServerUpdate, 2000);
                                }
                                else {
                                    runAlertDialog('Update failed!', function () {
                                        window.location.reload(true);
                                    });
                                }
                            }
                        });
                    }
                    
                    setTimeout(checkServerUpdate, 10000);
                });

                return false; /* prevents hiding the modal container */
            });
        }
    });
}

function doDownloadZipped(cameraId, groupKey) {
    showModalDialog('<div class="modal-progress"></div>', null, null, true);
    ajax('GET', '/picture/' + cameraId + '/zipped/' + groupKey + '/', null, function (data) {
        hideModalDialog(); /* progress */
        downloadFile('/picture/' + cameraId + '/zipped/' + groupKey + '/?key=' + data.key);
    });
}

function doDeleteFile(uri, callback) {
    var url = window.location.href;
    var parts = url.split('/');
    url = parts.slice(0, 3).join('/') + uri;
    
    runConfirmDialog('Really delete this file?', function () {
        ajax('POST', url, null, function (data) {
            if (data == null || data.error) {
                showErrorMessage(data && data.error);
                return;
            }

            if (callback) {
                callback();
            }
        });
    }, {stack: true});
}



    /* fetch & push */

function fetchCurrentConfig(onFetch) {
    function fetchCameraList() {
        /* fetch the camera list */
        ajax('GET', '/config/list/', null, function (data) {
            if (data == null || data.error) {
                showErrorMessage(data && data.error);
                data = {cameras: []};
                if (onFetch) {
                    onFetch(null);
                }
            }
            
            var i, cameras = data.cameras;
            
            if (user === 'admin') {
                var cameraSelect = $('#cameraSelect');
                cameraSelect.html('');
                for (i = 0; i < cameras.length; i++) {
                    var camera = cameras[i];
                    cameraSelect.append('<option value="' + camera['id'] + '">' + camera['name'] + '</option>');
                }
                cameraSelect.append('<option value="add">add camera...</option>');
                
                var enabledCameras = cameras.filter(function (camera) {return camera['enabled'];});
                if (enabledCameras.length > 0) { /* prefer the first enabled camera */
                    cameraSelect[0].selectedIndex = cameras.indexOf(enabledCameras[0]);
                    fetchCurrentCameraConfig();
                }
                else if (cameras.length) { /* a disabled camera */
                    cameraSelect[0].selectedIndex = 0;
                    fetchCurrentCameraConfig();
                }
                else { /* no camera at all */
                    cameraSelect[0].selectedIndex = -1;
                }

                updateConfigUi();
            }
            
            var mainLoadingProgressImg = $('img.main-loading-progress');
            if (mainLoadingProgressImg.length) {
                mainLoadingProgressImg.animate({'opacity': 0}, 200, function () {
                    recreateCameraFrames(cameras);
                    mainLoadingProgressImg.remove();
                });
            }
            else {
                recreateCameraFrames(cameras);
            }

            if (onFetch) {
                onFetch(data);
            }
        });
    }
    
    if (user === 'admin') {
        /* fetch the main configuration */
        ajax('GET', '/config/main/get/', null, function (data) {
            if (data == null || data.error) {
                showErrorMessage(data && data.error);
                return;
            }
            
            dict2MainUi(data);
            fetchCameraList();
        });
    }
    else {
        fetchCameraList();
    }
}

function fetchCurrentCameraConfig(onFetch) {
    var cameraId = $('#cameraSelect').val();
    if (cameraId != null) {
        ajax('GET', '/config/' + cameraId + '/get/', null, function (data) {
            if (data == null || data.error) {
                showErrorMessage(data && data.error);
                dict2CameraUi(null);
                if (onFetch) {
                    onFetch(null);
                }
                return;
            }
            
            dict2CameraUi(data);
            if (onFetch) {
                onFetch(data);
            }
        });
    }
    else {
        dict2CameraUi({});
    }
}

function pushMainConfig() {
    var mainConfig = mainUi2Dict();
    
    pushConfigs['main'] = mainConfig;
    if (!isApplyVisible()) {
        showApply();
    }
}

function pushCameraConfig() {
    var cameraConfig = cameraUi2Dict();
    var cameraId = $('#cameraSelect').val();

    pushConfigs[cameraId] = cameraConfig;
    if (!isApplyVisible()) {
        showApply();
    }
    
    /* also update the config stored in the camera frame div */
    var cameraFrame = $('div.camera-frame#camera' + cameraId);
    if (cameraFrame.length) {
        Object.update(cameraFrame[0].config, cameraConfig);
    }
}

function pushPreview(control) {
    var cameraId = $('#cameraSelect').val();
    
    var brightness = $('#brightnessSlider').val();
    var contrast= $('#contrastSlider').val();
    var saturation = $('#saturationSlider').val();
    var hue = $('#hueSlider').val();
    
    var data = {};
    
    if (brightness !== '' && (!control || control == 'brightness')) {
        data.brightness = brightness;
    }
    
    if (contrast !== '' && (!control || control == 'contrast')) {
        data.contrast = contrast;
    }
    
    if (saturation !== '' && (!control || control == 'saturation')) {
        data.saturation = saturation;
    }
    
    if (hue !== '' && (!control || control == 'hue')) {
        data.hue = hue;
    }
    
    refreshDisabled[cameraId] |= 0;
    refreshDisabled[cameraId]++;
    
    ajax('POST', '/config/' + cameraId + '/set_preview/', data, function (data) {
        refreshDisabled[cameraId]--;
        
        if (data == null || data.error) {
            showErrorMessage(data && data.error);
            return;
        }
    });
}

function getCameraIdsByInstance() {
    /* a motion instance is identified by the (host, port) pair;
     * the local instance has both the host and the port set to empty string */
    
    var cameraIdsByInstance = {};
    $('div.camera-frame').each(function () {
        var instance;
        if (this.config.proto == 'http' || this.config.proto == 'v4l2') {
            instance = '';
        }
        else { /* motioneye */
            instance = this.config.host || '';
            if (this.config.port) {
                instance += ':' + this.config.port;
            }
        }
        
        (cameraIdsByInstance[instance] = cameraIdsByInstance[instance] || []).push(this.config.id);
    });
    
    return cameraIdsByInstance;
}


    /* dialogs */

function runAlertDialog(message, onOk, options) {
    var params = {
        title: message,
        buttons: 'ok',
        onOk: onOk
    };
    
    if (options) {
        Object.update(params, options);
    }
    
    runModalDialog(params);
}

function runConfirmDialog(message, onYes, options) {
    var params = {
        title: message,
        buttons: 'yesno',
        onYes: onYes
    };
    
    if (options) {
        Object.update(params, options);
    }
    
    runModalDialog(params);
}

function runPictureDialog(entries, pos, mediaType) {
    var content = $('<div class="picture-dialog-content"></div>');
    
    var img = $('<img class="picture-dialog-content">');
    content.append(img);
    
    var prevArrow = $('<div class="picture-dialog-prev-arrow button mouse-effect" title="previous picture"></div>');
    content.append(prevArrow);
    
    var nextArrow = $('<div class="picture-dialog-next-arrow button mouse-effect" title="next picture"></div>');
    content.append(nextArrow);
    
    var progressImg = $('<img class="picture-dialog-progress" src="' + staticUrl + 'img/modal-progress.gif">');
    
    function updatePicture() {
        var entry = entries[pos];

        var windowWidth = $(window).width();
        var windowHeight = $(window).height();
        var widthCoef = windowWidth < 1000 ? 0.8 : 0.5;
        var heightCoef = 0.75;
        
        var width = parseInt(windowWidth * widthCoef);
        var height = parseInt(windowHeight * heightCoef);        
        
        prevArrow.css('display', 'none');
        nextArrow.css('display', 'none');
        img.parent().append(progressImg);
        updateModalDialogPosition();
        progressImg.css('left', (img.parent().width() - progressImg.width()) / 2);
        progressImg.css('top', (img.parent().height() - progressImg.height()) / 2);
        
        img.attr('src', '/' + mediaType + '/' + entry.cameraId + '/preview' + entry.path);
        img.load(function () {
            var aspectRatio = this.naturalWidth / this.naturalHeight;
            var sizeWidth = width * width / aspectRatio;
            var sizeHeight = height * aspectRatio * height;
            
            if (sizeWidth < sizeHeight) {
                img.width(width);
            }
            else {
                img.height(height);
            }
            updateModalDialogPosition();
            prevArrow.css('display', pos > 0 ? '' : 'none');
            nextArrow.css('display', pos < entries.length - 1 ? '' : 'none');
            progressImg.remove();
        });
        
        $('div.modal-container').find('span.modal-title:last').html(entry.name);
        updateModalDialogPosition();
    }
    
    prevArrow.click(function () {
        if (pos > 0) {
            pos--;
        }
        
        updatePicture();
    });
    
    nextArrow.click(function () {
        if (pos < entries.length - 1) {
            pos++;
        }
        
        updatePicture();
    });
    
    img.load(updateModalDialogPosition);
    
    runModalDialog({
        title: ' ',
        closeButton: true,
        buttons: [
            {caption: 'Close'},
            {caption: 'Download', isDefault: true, click: function () {
                var entry = entries[pos];
                downloadFile('/' + mediaType + '/' + entry.cameraId + '/download' + entry.path);
                
                return false;
            }}
        ],
        content: content,
        stack: true,
        onShow: updatePicture
    });
}

function runAddCameraDialog() {
    if (!$('#motionEyeSwitch')[0].checked) {
        return runAlertDialog('Please enable motionEye first!');
    }
    
    if (Object.keys(pushConfigs).length) {
        return runAlertDialog('Please apply the modified settings first!');
    }
    
    var content = 
            $('<table class="add-camera-dialog">' +
                '<tr>' +
                    '<td class="dialog-item-label"><span class="dialog-item-label">Device</span></td>' +
                    '<td class="dialog-item-value"><select class="styled" id="deviceSelect"></select></td>' +
                    '<td><span class="help-mark" title="the device you wish to add to motionEye">?</span></td>' +
                '</tr>' +
                '<tr class="motioneye netcam">' +
                    '<td class="dialog-item-label"><span class="dialog-item-label">URL</span></td>' +
                    '<td class="dialog-item-value"><input type="text" class="styled" id="urlEntry" placeholder="http://example.com:8080/cams/..."></td>' +
                    '<td><span class="help-mark" title="the camera URL (e.g. http://example.com:8080/cams/)">?</span></td>' +
                '</tr>' +
                '<tr class="motioneye netcam">' +
                    '<td class="dialog-item-label"><span class="dialog-item-label">Username</span></td>' +
                    '<td class="dialog-item-value"><input type="text" class="styled" id="usernameEntry" placeholder="username..."></td>' +
                    '<td><span class="help-mark" title="the username for the URL, if required (e.g. admin)">?</span></td>' +
                '</tr>' +
                '<tr class="motioneye netcam">' +
                    '<td class="dialog-item-label"><span class="dialog-item-label">Password</span></td>' +
                    '<td class="dialog-item-value"><input type="password" class="styled" id="passwordEntry" placeholder="password..."></td>' +
                    '<td><span class="help-mark" title="the password for the URL, if required">?</span></td>' +
                '</tr>' +
                '<tr class="motioneye netcam">' +
                    '<td class="dialog-item-label"><span class="dialog-item-label">Camera</span></td>' +
                    '<td class="dialog-item-value"><select class="styled" id="addCameraSelect"></select><span id="cameraMsgLabel"></span></td>' +
                    '<td><span class="help-mark" title="the camera you wish to add to motionEye">?</span></td>' +
                '</tr>' +
            '</table>');
    
    /* collect ui widgets */
    var deviceSelect = content.find('#deviceSelect');
    var urlEntry = content.find('#urlEntry');
    var usernameEntry = content.find('#usernameEntry');
    var passwordEntry = content.find('#passwordEntry');
    var addCameraSelect = content.find('#addCameraSelect');
    var cameraMsgLabel = content.find('#cameraMsgLabel');
    
    /* make validators */
    makeUrlValidator(urlEntry, true);
    makeTextValidator(usernameEntry, false);
    makeTextValidator(deviceSelect, false);
    makeComboValidator(addCameraSelect, true);
    
    /* ui interaction */
    content.find('tr.motioneye, tr.netcam').css('display', 'none');
    
    function updateUi() {
        content.find('tr.motioneye, tr.netcam').css('display', 'none');
        if (deviceSelect.val() == 'motioneye') {
            content.find('tr.motioneye').css('display', 'table-row');
            addCameraSelect.hide();
        }
        else if (deviceSelect.val() == 'netcam') {
            content.find('tr.netcam').css('display', 'table-row');
            addCameraSelect.hide();
        }
        
        updateModalDialogPosition();
        addCameraSelect.html('');
        
        /* re-validate all the validators */
        content.find('.validator').each(function () {
            this.validate();
        });
        
        if (content.is(':visible') && uiValid() && (deviceSelect.val() == 'motioneye' || deviceSelect.val() == 'netcam')) {
            fetchRemoteCameras();
        }
    }
    
    function uiValid(includeCameraSelect) {
        /* re-validate all the validators */
        content.find('.validator').each(function () {
            this.validate();
        });
        
        var valid = true;
        var query = content.find('input, select');
        if (!includeCameraSelect) {
            query = query.not('#addCameraSelect');
        }
        query.each(function () {
            if (this.invalid) {
                valid = false;
                return false;
            }
        });
        
        return valid;
    }
    
    function splitUrl(url) {
        var parts = url.split('://');
        var proto = parts[0];
        var index = parts[1].indexOf('/');
        var host = null;
        var uri = '';
        if (index >= 0) {
            host = parts[1].substring(0, index);
            uri = parts[1].substring(index);
        }
        else {
            host = parts[1];
        }
        
        var port = '';
        parts = host.split(':');
        if (parts.length >= 2) {
            host = parts[0];
            port = parts[1];
        }
        
        if (uri == '/') {
            uri = '';
        }
        
        return {
            proto: proto,
            host: host,
            port: port,
            uri: uri
        };
    }
    
    function fetchRemoteCameras() {
        var progress = $('<div style="text-align: center; margin: 2px;"><img src="' + staticUrl + 'img/small-progress.gif"></div>');
        
        addCameraSelect.hide();
        addCameraSelect.parent().find('div').remove(); /* remove any previous progress div */
        addCameraSelect.before(progress);
        
        var data = splitUrl(urlEntry.val());
        data.username = usernameEntry.val();
        data.password = passwordEntry.val();
        data.type = deviceSelect.val();
        
        cameraMsgLabel.html('');
        
        ajax('GET', '/config/list/', data, function (data) {
            progress.remove();
            
            if (data == null || data.error) {
                //showErrorMessage(data && data.error);
                cameraMsgLabel.html(data && data.error);
                
                return;
            }
            
            addCameraSelect.html('');
            
            if (data.error || !data.cameras) {
                return;
            }

            data.cameras.forEach(function (info) {
                addCameraSelect.append('<option value="' + info.id + '">' + info.name + '</option>');
            });
            
            addCameraSelect.show();
        });
    }
    
    deviceSelect.change(updateUi);
    urlEntry.change(updateUi);
    usernameEntry.change(updateUi);
    passwordEntry.change(updateUi);
    updateUi();
    
    showModalDialog('<div class="modal-progress"></div>');
    
    /* fetch the available devices */
    ajax('GET', '/config/list_devices/', null, function (data) {
        if (data == null || data.error) {
            hideModalDialog();
            showErrorMessage(data && data.error);
            return;
        }
        
        /* add available devices */
        data.devices.forEach(function (device) {
            if (!device.configured) {
                deviceSelect.append('<option value="' + device.uri + '">' + device.name + '</option>');
            }
        });
        
        deviceSelect.append('<option value="netcam">Network camera...</option>');
        deviceSelect.append('<option value="motioneye">Remote motionEye camera...</option>');
        
        updateUi();
        
        runModalDialog({
            title: 'Add Camera...',
            closeButton: true,
            buttons: 'okcancel',
            content: content,
            onOk: function () {
                if (!uiValid(true)) {
                    return false;
                }

                var data = {};
                
                if (deviceSelect.val() == 'motioneye') {
                    data = splitUrl(urlEntry.val());
                    data.proto = 'motioneye';
                    data.username = usernameEntry.val();
                    data.password = passwordEntry.val();
                    data.remote_camera_id = addCameraSelect.val();
                }
                else if (deviceSelect.val() == 'netcam') {
                    data = splitUrl(urlEntry.val());
                    data.username = usernameEntry.val();
                    data.password = passwordEntry.val();
                }
                else { /* assuming v4l2 */
                    data.proto = 'v4l2';
                    data.uri = deviceSelect.val();
                }

                beginProgress();
                ajax('POST', '/config/add/', data, function (data) {
                    if (data == null || data.error) {
                        endProgress();
                        showErrorMessage(data && data.error);
                        return;
                    }
                    
                    endProgress();
                    var cameraOption = $('#cameraSelect').find('option[value=add]');
                    cameraOption.before('<option value="' + data.id + '">' + data.name + '</option>');
                    $('#cameraSelect').val(data.id).change();
                    recreateCameraFrames();
                });
            }
        });
    });
}

function runTimelapseDialog(cameraId, groupKey, group) {
    var content = 
            $('<table class="timelapse-dialog">' +
                '<tr>' +
                    '<td class="dialog-item-label"><span class="dialog-item-label">Group</span></td>' +
                    '<td class="dialog-item-value">' + groupKey + '</td>' +
                '</tr>' +
                '<tr>' +
                    '<td class="dialog-item-label"><span class="dialog-item-label">Include a picture taken every</span></td>' +
                    '<td class="dialog-item-value">' +
                        '<select class="styled timelapse" id="intervalSelect">' + 
                            '<option value="1">second</option>' +
                            '<option value="5">5 seconds</option>' +
                            '<option value="10">10 seconds</option>' +
                            '<option value="30">30 seconds</option>' +
                            '<option value="60">minute</option>' +
                            '<option value="300">5 minutes</option>' +
                            '<option value="600">10 minutes</option>' +
                            '<option value="1800">30 minutes</option>' +
                            '<option value="3600">hour</option>' +
                        '</select>' +
                    '</td>' +
                    '<td><span class="help-mark" title="choose the interval of time between two selected pictures">?</span></td>' +
                '</tr>' +
                '<tr>' +
                    '<td class="dialog-item-label"><span class="dialog-item-label">Movie framerate</span></td>' +
                    '<td class="dialog-item-value"><input type="text" class="styled range" id="framerateSlider"></td>' +
                    '<td><span class="help-mark" title="choose how fast you want the timelapse playback to be">?</span></td>' +
                '</tr>' +
            '</table>');

    var intervalSelect = content.find('#intervalSelect');
    var framerateSlider = content.find('#framerateSlider');
    
    makeSlider(framerateSlider, 1, 100, 0, [
        {value: 1, label: '1'},
        {value: 20, label: '20'},
        {value: 40, label: '40'},
        {value: 60, label: '60'},
        {value: 80, label: '80'},
        {value: 100, label: '100'}
    ], null, 0);
    
    intervalSelect.val(60);
    framerateSlider.val(20).each(function () {this.update()});

    runModalDialog({
        title: 'Create Timelapse Movie',
        closeButton: true,
        buttons: 'okcancel',
        content: content,
        onOk: function () {
            showModalDialog('<div class="modal-progress"></div>', null, null, true);
            ajax('GET', '/picture/' + cameraId + '/timelapse/' + groupKey + '/',
                    {interval: intervalSelect.val(), framerate: framerateSlider.val()}, function (data) {

                hideModalDialog(); /* progress */
                hideModalDialog(); /* timelapse dialog */
                downloadFile('/picture/' + cameraId + '/timelapse/' + groupKey + '/?key=' + data.key);
            });

            return false;
        },
        stack: true
    });
}

function runMediaDialog(cameraId, mediaType) {
    var dialogDiv = $('<div class="media-dialog"></div>');
    var mediaListDiv = $('<div class="media-dialog-list"></div>');
    var groupsDiv = $('<div class="media-dialog-groups"></div>');
    var buttonsDiv = $('<div class="media-dialog-buttons"></div>');
    
    var groups = {};
    var groupKey = null;
    
    dialogDiv.append(groupsDiv);
    dialogDiv.append(mediaListDiv);
    
    if (mediaType == 'picture') {
        dialogDiv.append(buttonsDiv);
        
        var zippedButton = $('<div class="media-dialog-button">Zipped Pictures</div>');
        buttonsDiv.append(zippedButton);
        
        zippedButton.click(function () {
            if (groupKey) {
                doDownloadZipped(cameraId, groupKey);
            }
        });
        
        var timelapseButton = $('<div class="media-dialog-button">Timelapse Movie</div>');
        buttonsDiv.append(timelapseButton);
        
        timelapseButton.click(function () {
            if (groupKey) {
                runTimelapseDialog(cameraId, groupKey, groups[groupKey]);
            }
        });
    }
    
    function updateDialogSize() {
        var windowWidth = $(window).width();
        var windowHeight = $(window).height();
        
        if (Object.keys(groups).length == 0) {
            groupsDiv.width('auto');
            groupsDiv.height('auto');
            groupsDiv.addClass('small-screen');
            mediaListDiv.width('auto');
            mediaListDiv.height('auto');
            buttonsDiv.hide();

            return;
        }
        
        buttonsDiv.show();
        
        if (windowWidth < 1000) {
            groupsDiv.width(parseInt(windowWidth * 0.8));
            groupsDiv.height('');
            groupsDiv.addClass('small-screen');
            mediaListDiv.width(parseInt(windowWidth * 0.8));
            mediaListDiv.height(parseInt(windowHeight * 0.7));
        }
        else {
            mediaListDiv.width(parseInt(windowWidth * 0.7));
            mediaListDiv.height(parseInt(windowHeight * 0.7));
            groupsDiv.height(parseInt(windowHeight * 0.7));
            groupsDiv.width('');
            groupsDiv.removeClass('small-screen');
        }
    }
    
    function onResize() {
        updateDialogSize();
        updateModalDialogPosition();
    }
    
    $(window).resize(onResize);
    
    updateDialogSize();
    
    showModalDialog('<div class="modal-progress"></div>');
    
    /* fetch the media list */
    ajax('GET', '/' + mediaType + '/' + cameraId + '/list/', null, function (data) {
        if (data == null || data.error) {
            hideModalDialog();
            showErrorMessage(data && data.error);
            return;
        }
        
        /* group the media */
        data.mediaList.forEach(function (media) {
            var path = media.path;
            var parts = path.split('/');
            var keyParts = parts.splice(0, parts.length - 1);
            var key = keyParts.join('/');
            
            if (key.indexOf('/') === 0) {
                key = key.substring(1);
            }
            
            var list = (groups[key] = groups[key] || []);
            
            list.push({
                'path': path,
                'group': key,
                'name': parts[parts.length - 1],
                'cameraId': cameraId
            });
        });
        
        updateDialogSize();
        
        var keys = Object.keys(groups);
        keys.sort();
        keys.reverse();
        
        /* add a temporary div to compute 3em in px */
        var tempDiv = $('<div style="width: 3em; height: 3em;"></div>');
        $('div.modal-container').append(tempDiv);
        var height = tempDiv.height();
        tempDiv.remove();

        function showGroup(key) {
            groupKey = key;
            
            if (mediaListDiv.find('img.media-list-progress').length) {
                return; /* already in progress of loading */
            }
            
            /* (re)set the current state of the group buttons */
            groupsDiv.find('div.media-dialog-group-button').each(function () {
                var $this = $(this);
                if (this.key == key) {
                    $this.addClass('current');
                }
                else {
                    $this.removeClass('current');
                }
            });
            
            var mediaListByName = {};
            var entries = groups[key];
            
            /* cleanup the media list */
            mediaListDiv.children('div.media-list-entry').detach();
            mediaListDiv.html('');
            
            function addEntries() {
                /* add the entries to the media list */
                entries.forEach(function (entry) {
                    var entryDiv = entry.div;
                    var detailsDiv = null;
                    
                    if (!entryDiv) {
                        entryDiv = $('<div class="media-list-entry"></div>');
                        
                        var previewImg = $('<img class="media-list-preview" src="' + staticUrl + 'img/modal-progress.gif"/>');
                        entryDiv.append(previewImg);
                        previewImg[0]._src = '/' + mediaType + '/' + cameraId + '/preview' + entry.path + '?height=' + height;
                        
                        var downloadButton = $('<div class="media-list-download-button button">Download</div>');
                        entryDiv.append(downloadButton);
                        
                        var deleteButton = $('<div class="media-list-delete-button button">Delete</div>');
                        
                        if (user === 'admin') {
                            entryDiv.append(deleteButton);
                        }

                        var nameDiv = $('<div class="media-list-entry-name">' + entry.name + '</div>');
                        entryDiv.append(nameDiv);
                        
                        detailsDiv = $('<div class="media-list-entry-details"></div>');
                        entryDiv.append(detailsDiv);
                        
                        downloadButton.click(function () {
                            downloadFile('/' + mediaType + '/' + cameraId + '/download' + entry.path);
                            return false;
                        });
                        
                        deleteButton.click(function () {
                            doDeleteFile('/' + mediaType + '/' + cameraId + '/delete' + entry.path, function () {
                                entryDiv.remove();
                            });
                            
                            return false;
                        });

                        entryDiv.click(function () {
                            var pos = entries.indexOf(entry);
                            runPictureDialog(entries, pos, mediaType);
                        });
                        
                        entry.div = entryDiv;
                    }
                    else {
                        detailsDiv = entry.div.find('div.media-list-entry-details');
                    }                    
                    
                    var momentSpan = $('<span class="details-moment">' + entry.momentStr + ', </span>');
                    var momentShortSpan = $('<span class="details-moment-short">' + entry.momentStrShort + '</span>');
                    var sizeSpan = $('<span class="details-size">' + entry.sizeStr + '</span>');
                    detailsDiv.empty();
                    detailsDiv.append(momentSpan);
                    detailsDiv.append(momentShortSpan);
                    detailsDiv.append(sizeSpan);
                    mediaListDiv.append(entryDiv);
                });

                /* trigger a scroll event */
                mediaListDiv.scroll();
            }
            
            /* if details are already fetched, simply add the entries and return */
            if (entries[0].timestamp) {
                return addEntries();
            }
            
            var previewImg = $('<img class="media-list-progress" src="' + staticUrl + 'img/modal-progress.gif"/>');
            mediaListDiv.append(previewImg);
            
            var url = '/' + mediaType + '/' + cameraId + '/list/?prefix=' + (key || 'ungrouped');
            ajax('GET', url, null, function (data) {
                previewImg.remove();
                
                if (data == null || data.error) {
                    hideModalDialog();
                    showErrorMessage(data && data.error);
                    return;
                }
                
                /* index the media list by name */
                data.mediaList.forEach(function (media) {
                    var path = media.path;
                    var parts = path.split('/');
                    var name = parts[parts.length - 1];
                    
                    mediaListByName[name] = media;
                });
                
                /* assign details to entries */
                entries.forEach(function (entry) {
                    var media = mediaListByName[entry.name];
                    if (media) {
                        entry.momentStr = media.momentStr;
                        entry.momentStrShort = media.momentStrShort;
                        entry.sizeStr = media.sizeStr;
                        entry.timestamp = media.timestamp;
                    }
                });
 
                /* sort the entries by timestamp */
                entries.sortKey(function (e) {return e.timestamp || e.name;}, true);
                
                addEntries();
            });
        }
        
        if (keys.length) {
            keys.forEach(function (key) {
                var groupButton = $('<div class="media-dialog-group-button"></div>');
                groupButton.text(key || '(ungrouped)');
                groupButton[0].key = key;
                
                groupButton.click(function () {
                    showGroup(key);
                });
                
                groupsDiv.append(groupButton);
            });
        }
        else {
            groupsDiv.html('(no media files)');
            mediaListDiv.remove();
        }
        
        var title;
        if (mediaType === 'picture') {
            title = 'Pictures taken by ' + data.cameraName;
        }
        else {
            title = 'Movies recorded by ' + data.cameraName;
        }
        
        runModalDialog({
            title: title,
            closeButton: true,
            buttons: '',
            content: dialogDiv,
            onShow: function () {
                //dialogDiv.scrollTop(dialogDiv.prop('scrollHeight'));
                if (keys.length) {
                    showGroup(keys[0]);
                }
            },
            onClose: function () {
                $(window).unbind('resize', onResize);
            }
        });
    });
    
    /* install the media list scroll event handler */
    mediaListDiv.scroll(function () {
        var height = mediaListDiv.height();
        
        mediaListDiv.find('img.media-list-preview').each(function () {
            if (!this._src) {
                return;
            }
            
            var $this = $(this);
            var entryDiv = $this.parent();
            
            var top1 = entryDiv.position().top;
            var top2 = top1 + entryDiv.height();
            
            if ((top1 >= 0 && top1 <= height) ||
                (top2 >= 0 && top2 <= height)) {
                
                this.src = this._src;
                delete this._src;
            }
        });
    });
}


    /* camera frames */

function addCameraFrameUi(cameraConfig) {
    var pageContainer = $('div.page-container');
    
    if (cameraConfig == null) {
        var cameraFrameDivPlaceHolder = $('<div class="camera-frame-place-holder"></div>');
        pageContainer.append(cameraFrameDivPlaceHolder);
        
        return;
    }
    
    var cameraId = cameraConfig.id;
    
    var cameraFrameDiv = $(
            '<div class="camera-frame">' +
                '<div class="camera-top-bar">' +
                    '<span class="camera-name"></span>' +
                    '<div class="camera-buttons">' +
                        '<div class="button camera-button mouse-effect full-screen" title="full-screen window"></div>' +
                        '<div class="button camera-button mouse-effect media-pictures" title="pictures"></div>' +
                        '<div class="button camera-button mouse-effect media-movies" title="movies"></div>' +
                        '<div class="button camera-button mouse-effect configure" title="configure"></div>' +
                    '</div>' +
                '</div>' +
                '<div class="camera-container">' +
                    '<div class="camera-placeholder"><img class="no-camera" src="' + staticUrl + 'img/no-camera.svg"></div>' +
                    '<img class="camera">' +
                    '<div class="camera-progress"><img class="camera-progress"></div>' +
                '</div>' +
            '</div>');
    
    var nameSpan = cameraFrameDiv.find('span.camera-name');
    var configureButton = cameraFrameDiv.find('div.camera-button.configure');
    var picturesButton = cameraFrameDiv.find('div.camera-button.media-pictures');
    var moviesButton = cameraFrameDiv.find('div.camera-button.media-movies');
    var fullScreenButton = cameraFrameDiv.find('div.camera-button.full-screen');
    var cameraPlaceholder = cameraFrameDiv.find('div.camera-placeholder');
    var cameraProgress = cameraFrameDiv.find('div.camera-progress');
    var cameraImg = cameraFrameDiv.find('img.camera');
    var progressImg = cameraFrameDiv.find('img.camera-progress');
    
    /* no camera buttons if not admin */
    if (user !== 'admin') {
        configureButton.hide();
    }
    
    cameraFrameDiv.attr('id', 'camera' + cameraId);
    cameraFrameDiv[0].refreshDivider = 0;
    cameraFrameDiv[0].config = cameraConfig;
    nameSpan.html(cameraConfig.name);
    progressImg.attr('src', staticUrl + 'img/camera-progress.gif');
    
    cameraProgress.click(function () {
        doFullScreenCamera(cameraId);
    });
    
    cameraProgress.addClass('visible');
    cameraPlaceholder.css('opacity', '0');
    
    /* insert the new camera frame at the right position,
     * with respect to the camera id */
    var cameraFrames = pageContainer.find('div.camera-frame');
    var cameraIds = cameraFrames.map(function () {return parseInt(this.id.substring(6));});
    cameraIds.sort();
    
    var index = 0; /* find the first position that is greater than the current camera id */
    while (index < cameraIds.length && cameraIds[index] < cameraId) {
        index++;
    }
    
    if (index < cameraIds.length) {
        var beforeCameraFrame = pageContainer.find('div.camera-frame#camera' + cameraIds[index]);
        cameraFrameDiv.insertAfter(beforeCameraFrame);
    }
    else  {
        pageContainer.append(cameraFrameDiv);
    }

    /* fade in */
    cameraFrameDiv.animate({'opacity': 1}, 100);
    
    /* add the button handlers */
    configureButton.click(function () {
        doConfigureCamera(cameraId);
    });

    picturesButton.click(function (cameraId) {
        return function () {
            runMediaDialog(cameraId, 'picture');
        };
    }(cameraId));
    
    moviesButton.click(function (cameraId) {
        return function () {
            runMediaDialog(cameraId, 'movie');
        };
    }(cameraId));
    
    fullScreenButton.click(function (cameraId) {
        return function () {
            window.open(window.location.href + 'picture/' + cameraId + '/frame/', '_blank');
        };
    }(cameraId));
    
    /* error and load handlers */
    cameraImg.error(function () {
        this.error = true;
        this.loading = 0;
        
        cameraImg.addClass('error').removeClass('loading');
        cameraImg.height(Math.round(cameraImg.width() * 0.75));
        cameraPlaceholder.css('opacity', 1);
        cameraProgress.removeClass('visible');
    });
    cameraImg.load(function () {
        if (refreshDisabled[cameraId]) {
            return; /* refresh temporarily disabled for updating */
        }
        
        this.error = false;
        this.loading = 0;
        
        cameraImg.removeClass('error').removeClass('loading');
        cameraImg.css('height', '');
        cameraPlaceholder.css('opacity', 0);
        cameraProgress.removeClass('visible');
        
        if (fullScreenCameraId) {
            /* update the modal dialog position when image is loaded */
            updateModalDialogPosition();
        }
    });
    
    cameraImg.addClass('loading');
    cameraImg.height(Math.round(cameraImg.width() * 0.75));
}

function remCameraFrameUi(cameraId) {
    var pageContainer = $('div.page-container');
    var cameraFrameDiv = pageContainer.find('div.camera-frame#camera' + cameraId);
    cameraFrameDiv.animate({'opacity': 0}, 100, function () {
        cameraFrameDiv.remove();
    });
}

function recreateCameraFrames(cameras) {
    var pageContainer = $('div.page-container');
    
    function updateCameras(cameras) {
        cameras = cameras.filter(function (camera) {return camera.enabled;});
        var i, camera;

        /* remove everything on the page */
        pageContainer.children().remove();
        
        /* add camera frames */
        for (i = 0; i < cameras.length; i++) {
            camera = cameras[i];
            addCameraFrameUi(camera);
        }
        
        if ($('#cameraSelect').find('option').length < 2 && user === 'admin' && $('#motionEyeSwitch')[0].checked) {
            /* invite the user to add a camera */
            var addCameraLink = $('<div class="add-camera-message">' + 
                    '<a href="javascript:runAddCameraDialog()">You have not configured any camera yet. Click here to add one...</a></div>');
            pageContainer.append(addCameraLink);
        }
    }
    
    if (cameras != null) {
        updateCameras(cameras);
    }
    else {
        ajax('GET', '/config/list/', null, function (data) {
            if (data == null || data.error) {
                showErrorMessage(data && data.error);
                return;
            }
            
            updateCameras(data.cameras);
        });
    }
}


function doConfigureCamera(cameraId) {
    if (inProgress) {
        return;
    }
    
    openSettings(cameraId);
}

function doFullScreenCamera(cameraId) {
    if (inProgress || refreshCameraFrames[cameraId]) {
        return;
    }
    
    if (fullScreenCameraId != null) {
        return; /* a camera is already in full screen */
    }
    
    fullScreenCameraId = -1; /* avoids successive fast toggles of fullscreen */
    
    var cameraFrameDiv = $('#camera' + cameraId);
    var cameraName = cameraFrameDiv.find('span.camera-name').text();
    var frameImg = cameraFrameDiv.find('img.camera');
    var aspectRatio = frameImg.width() / frameImg.height();
    var windowWidth = $(window).width();
    var windowHeight = $(window).height();
    var windowAspectRatio = windowWidth / windowHeight;
    var frameIndex = cameraFrameDiv.index();
    var pageContainer = $('div.page-container');
    
    if (frameImg.hasClass('error')) {
        return; /* no full screen for erroneous cameras */
    }

    var width;
    if (windowAspectRatio > aspectRatio) {
        width = aspectRatio * Math.round(0.8 * windowHeight);
    }
    else {
        width = Math.round(0.9 * windowWidth);
    }

    cameraFrameDiv.find('div.camera-progress').addClass('visible');
    
    var cameraImg = cameraFrameDiv.find('img.camera');
    cameraImg.load(function showFullScreenCamera() {
        cameraFrameDiv.css('width', width);
        fullScreenCameraId = cameraId;
        
        runModalDialog({
            title: cameraName,
            closeButton: true,
            content: cameraFrameDiv,
            onShow: function () {
                cameraImg.unbind('load', showFullScreenCamera);
            },
            onClose: function () {
                fullScreenCameraId = null;
                cameraFrameDiv.css('width', '');
                var nextFrame = pageContainer.children('div:eq(' + frameIndex + ')');
                if (nextFrame.length) {
                    nextFrame.before(cameraFrameDiv);
                }
                else {
                    pageContainer.append(cameraFrameDiv);
                }
            }
        });
    });
}

function refreshCameraFrames() {
    function refreshCameraFrame(cameraId, img, serverSideResize) {
        if (refreshDisabled[cameraId]) {
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
        if (serverSideResize) {
            uri += '&width=' + img.width;
        }
        
        img.src = uri;
        img.loading = 1;
    }

    var cameraFrames;
    if (fullScreenCameraId != null && fullScreenCameraId >= 0) {
        cameraFrames = $('#camera' + fullScreenCameraId);
    }
    else {
        cameraFrames = $('div.page-container').find('div.camera-frame');
    }
    
    cameraFrames.each(function () {
        /* limit the refresh rate to 20 fps */
        var count = Math.max(1, 1 / this.config['streaming_framerate'] * 1000 / refreshInterval);
        var serverSideResize = this.config['streaming_server_resize'];
        var img = $(this).find('img.camera')[0];
        
        if (img.error) {
            /* in case of error, decrease the refresh rate to 1 fps */
            count = 1000 / refreshInterval;
        }
        
        if (this.refreshDivider < count) {
            this.refreshDivider++;
        }
        else {
            var cameraId = this.id.substring(6);
            refreshCameraFrame(cameraId, img, serverSideResize); /* count <= 2 means at least 5 fps */
            
            this.refreshDivider = 0;
        }
    });
    
    setTimeout(refreshCameraFrames, refreshInterval);
}

function checkCameraErrors() {
    /* properly triggers the onerror event on the cameras whose imgs were not successfully loaded,
     * but the onerror event hasn't been triggered, for some reason (seems to happen in Chrome) */
    var cameraFrames = $('div.page-container').find('img.camera');
    
    cameraFrames.each(function () {
        if (this.complete === true && this.naturalWidth === 0 && !this.error && this.src) {
            $(this).error();
        }
    });
    
    setTimeout(checkCameraErrors, 500);
}


    /* startup function */

$(document).ready(function () {
    /* open/close settings */
    $('div.settings-button').click(function () {
        if (isSettingsOpen()) {
             closeSettings();
        }
        else {
            openSettings();
        }
    });
    
    /* software update button */
    $('div#updateButton').click(doUpdate);
    
    /* prevent scroll events on settings div from propagating TODO this does not actually work */
    $('div.settings').mousewheel(function (e, d) {
        var t = $(this);
        if (d > 0 && t.scrollTop() === 0) {
            e.preventDefault();
        }
        else if (d < 0 && (t.scrollTop() === t.get(0).scrollHeight - t.innerHeight())) {
            e.preventDefault();
        }
    });
    
    initUI();
    beginProgress();
    fetchCurrentConfig(endProgress);
    refreshCameraFrames();
    checkCameraErrors();
});

