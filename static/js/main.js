
var pushConfigs = {};
var refreshDisabled = 0;


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


    /* UI initialization */

function initUI() {
    /* checkboxes */
    $('input[type=checkbox].styled').each(function () {
        makeCheckBox($(this));
    });

    /* sliders */
    makeSlider($('#brightnessSlider'), 0, 100, 0, null, 5, 0, '%');
    makeSlider($('#contrastSlider'), 0, 100, 0, null, 5, 0, '%');
    makeSlider($('#saturationSlider'), 0, 100, 0, null, 5, 0, '%');
    makeSlider($('#hueSlider'), 0, 100, 0, null, 5, 0, '%');
    makeSlider($('#framerateSlider'), 1, 30, 0, [
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
    makeSlider($('#streamingQualitySlider'), 0, 100, 0, null, 5, 0, '%');
    makeSlider($('#imageQualitySlider'), 0, 100, 0, null, 5, 0, '%');
    makeSlider($('#movieQualitySlider'), 0, 100, 0, null, 5, 0, '%');
    makeSlider($('#frameChangeThresholdSlider'), 0, 10000, 0, null, 3, 0, 'px');
    makeSlider($('#noiseLevelSlider'), 0, 100, 0, null, 5, 0, '%');
    
    /* text validators */
    makeTextValidator($('#adminUsernameEntry'), true);
    makeTextValidator($('#normalUsernameEntry'), true);
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
    
    /* number validators */
    makeNumberValidator($('#streamingPortEntry'), 1024, 65535, false, false, true);
    makeNumberValidator($('#snapshotIntervalEntry'), 1, 86400, false, false, true);
    makeNumberValidator($('#gapEntry'), 1, 86400, false, false, true);
    makeNumberValidator($('#preCaptureEntry'), 0, 100, false, false, true);
    makeNumberValidator($('#postCaptureEntry'), 0, 100, false, false, true);
    
    /* time validators */
    makeTimeValidator($('#mondayFrom'));
    makeTimeValidator($('#mondayTo'));
    makeTimeValidator($('#tuesdayFrom'));
    makeTimeValidator($('#tuesdayTo'));
    makeTimeValidator($('#wednesdayFrom'));
    makeTimeValidator($('#wednesdayTo'));
    makeTimeValidator($('#thursdayFrom'));
    makeTimeValidator($('#thursdayTo'));
    makeTimeValidator($('#fridayFrom'));
    makeTimeValidator($('#fridayTo'));
    makeTimeValidator($('#saturdayFrom'));
    makeTimeValidator($('#saturdayTo'));
    makeTimeValidator($('#sundayFrom'));
    makeTimeValidator($('#sundayTo'));
    
    /* ui elements that enable/disable other ui elements */
    $('#motionEyeSwitch').change(updateConfigUi);
    $('#showAdvancedSwitch').change(updateConfigUi);
    $('#storageDeviceSelect').change(updateConfigUi);
    $('#autoBrightnessSwitch').change(updateConfigUi);
    $('#leftTextSelect').change(updateConfigUi);
    $('#rightTextSelect').change(updateConfigUi);
    $('#captureModeSelect').change(updateConfigUi);
    $('#autoNoiseDetectSwitch').change(updateConfigUi);
    $('#videoDeviceSwitch').change(updateConfigUi);
    $('#textOverlaySwitch').change(updateConfigUi);
    $('#videoStreamingSwitch').change(updateConfigUi);
    $('#stillImagesSwitch').change(updateConfigUi);
    $('#motionMoviesSwitch').change(updateConfigUi);
    $('#motionNotificationsSwitch').change(updateConfigUi);
    $('#workingScheduleSwitch').change(updateConfigUi);
    
    /* fetch & push handlers */
    $('#videoDeviceSelect').change(function () {
        if ($('#videoDeviceSelect').val() === 'add') {
            runAddCameraDialog();
            if ($('#videoDeviceSelect').find('option').length > 1) {
                $('#videoDeviceSelect')[0].selectedIndex = 0;
            }
            else {
                $('#videoDeviceSelect')[0].selectedIndex = -1;
            }
            
            updateConfigUi();
        }
        else {
            fetchCurrentCameraConfig();
        }
    });
    $('input.general').change(pushMainConfig);
    $('input.device, select.device, ' +
      'input.storage, select.storage, ' +
      'input.text-overlay, select.text-overlay, ' + 
      'input.streaming, select.streaming, ' +
      'input.still-images, select.still-images, ' +
      'input.motion-movies, select.motion-movies, ' +
      'input.motion-detection, select.motion-detection, ' +
      'input.notifications, select.notifications, ' +
      'input.working-schedule, select.working-schedule').change(pushCameraConfig);
    
    /* preview controls */
    $('#brightnessSlider').change(pushPreview);
    $('#contrastSlider').change(pushPreview);
    $('#saturationSlider').change(pushPreview);
    $('#hueSlider').change(pushPreview);
    
    /* apply button */
    $('#applyButton').click(function () {
        if ($(this).hasClass('progress')) {
            return; /* in progress */
        }
        
        doApply();
    });
    
    /* whenever the window is resized,
     * if a modal dialog is visible, it should be repositioned */
    $(window).resize(updateModalDialogPosition);
    
    /* remove camera button */
    $('div.button.rem-camera-button').click(doRemCamera);
}


    /* settings */

function openSettings(cameraId) {
    if (cameraId != null) {
        $('#videoDeviceSelect').val(cameraId).change();
    }
    
    $('div.settings').addClass('open');
    $('div.page-container').addClass('stretched');
    $('div.settings-top-bar').addClass('open');
    
    updateConfigUi();
}

function closeSettings() {
    hideApply();
    
    $('div.settings').removeClass('open');
    $('div.page-container').removeClass('stretched');
    $('div.settings-top-bar').removeClass('open');
}

function isSettingsOpen() {
    return $('div.settings').hasClass('open');   
}

function updateConfigUi() {
    var objs = $('tr.settings-item, div.advanced-setting, table.advanced-setting, div.settings-section-title, table.settings').not('.rpi');
    
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
    
    if ($('#videoDeviceSelect').find('option').length < 2) { /* no camera configured */
        $('#videoDeviceSwitch').parent().each(markHide);
        $('#videoDeviceSwitch').parent().nextAll('div.settings-section-title, table.settings').each(markHide);
    }
    
    /* advanced settings */
    var showAdvanced = $('#showAdvancedSwitch').get(0).checked;
    if (!showAdvanced) {
        $('tr.advanced-setting, div.advanced-setting, table.advanced-setting').each(markHide);
    }
    
    /* storage device */
    if ($('#storageDeviceSelect').val() === 'local-disk') {
        $('#networkServerEntry').parents('tr:eq(0)').each(markHide);
        $('#networkUsernameEntry').parents('tr:eq(0)').each(markHide);
        $('#networkPasswordEntry').parents('tr:eq(0)').each(markHide);
        $('#networkShareNameEntry').parents('tr:eq(0)').each(markHide);
    }
    
    /* auto brightness */
    if ($('#autoBrightnessSwitch').get(0).checked) {
        $('#brightnessSlider').parents('tr:eq(0)').each(markHide);
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
    
    /* video streaming switch */
    if (!$('#videoStreamingSwitch').get(0).checked) {
        $('#videoStreamingSwitch').parent().next('table.settings').find('tr.settings-item').each(markHide);
    }
    
    /* still images switch */
    if (!$('#stillImagesSwitch').get(0).checked) {
        $('#stillImagesSwitch').parent().next('table.settings').find('tr.settings-item').each(markHide);
    }
    
    /* motion movies switch */
    if (!$('#motionMoviesSwitch').get(0).checked) {
        $('#motionMoviesSwitch').parent().next('table.settings').find('tr.settings-item').each(markHide);
    }
    
    /* motion notifications switch */
    if (!$('#motionNotificationsSwitch').get(0).checked) {
        $('#motionNotificationsSwitch').parent().next('table.settings').find('tr.settings-item').each(markHide);
    }
    
    /* working schedule switch */
    if (!$('#workingScheduleSwitch').get(0).checked) {
        $('#workingScheduleSwitch').parent().next('table.settings').find('tr.settings-item').each(markHide);
    }
    
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
    $('div.settings').find('select').each(function () {
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
        'normal_password': $('#normalPasswordEntry').val()
    };
}

function dict2MainUi(dict) {
    $('#motionEyeSwitch')[0].checked = dict['enabled'];
    $('#showAdvancedSwitch')[0].checked = dict['show_advanced'];
    $('#adminUsernameEntry').val(dict['admin_username']);
    $('#adminPasswordEntry').val(dict['admin_password']);
    $('#normalUsernameEntry').val(dict['normal_username']);
    $('#normalPasswordEntry').val(dict['normal_password']);
    
    updateConfigUi();
}

function cameraUi2Dict() {
    var dict = {
        /* video device */
        'enabled': $('#videoDeviceSwitch')[0].checked,
        'name': $('#deviceNameEntry').val(),
        'proto': $('#deviceEntry').val().split('://')[0],
        'device': $('#deviceEntry').val().split('://')[1],
        'light_switch_detect': $('#lightSwitchDetectSwitch')[0].checked,
        'auto_brightness': $('#autoBrightnessSwitch')[0].checked,
        'resolution': $('#resolutionSelect').val(),
        'rotation': $('#rotationSelect').val(),
        'framerate': $('#framerateSlider').val(),
        
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
        'streaming_port': $('#streamingPortEntry').val(),
        'streaming_framerate': $('#streamingFramerateSlider').val(),
        'streaming_quality': $('#streamingQualitySlider').val(),
        'streaming_motion': $('#streamingMotion')[0].checked,
        
        /* still images */
        'still_images': $('#stillImagesSwitch')[0].checked,
        'image_file_name': $('#imageFileNameEntry').val(),
        'image_quality': $('#imageQualitySlider').val(),
        'capture_mode': $('#captureModeSelect').val(),
        'snapshot_interval': $('#snapshotIntervalEntry').val(),
        'preserve_images': $('#preserveImagesSelect').val(),
        
        /* motion movies */
        'motion_movies': $('#motionMoviesSwitch')[0].checked,
        'movie_file_name': $('#movieFileNameEntry').val(),
        'movie_quality': $('#movieQualitySlider').val(),
        'preserve_movies': $('#preserveMoviesSelect').val(),
        
        /* motion detection */
        'show_frame_changes': $('#showFrameChangesSwitch')[0].checked,
        'frame_change_threshold': $('#frameChangeThresholdSlider').val(),
        'auto_noise_detect': $('#autoNoiseDetectSwitch')[0].checked,
        'noise_level': $('#noiseLevelSlider').val(),
        'gap': $('#gapEntry').val(),
        'pre_capture': $('#preCaptureEntry').val(),
        'post_capture': $('#postCaptureEntry').val(),
        
        /* motion notifications */
        'motion_notifications': $('#motionNotificationsSwitch')[0].checked,
        'motion_notifications_emails': $('#emailAddressesEntry').val(),
        
        /* working schedule */
        'working_schedule': $('#workingScheduleSwitch')[0].checked,
        'monday_from': $('#mondayFrom').val(),
        'monday_to':$('#mondayTo').val(),
        'tuesday_from': $('#tuesdayFrom').val(),
        'tuesday_to': $('#tuesdayTo').val(),
        'wednesday_from': $('#wednesdayFrom').val(),
        'wednesday_to': $('#wednesdayTo').val(),
        'thursday_from': $('#thursdayFrom').val(),
        'thursday_to': $('#thursdayTo').val(),
        'friday_from':$('#fridayFrom').val(),
        'friday_to': $('#fridayTo').val(),
        'saturday_from':$('#saturdayFrom').val(),
        'saturday_to': $('#saturdayTo').val(),
        'sunday_from': $('#sundayFrom').val(),
        'sunday_to': $('#sundayTo').val(),
    };

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
    /* video device */
    $('#videoDeviceSwitch')[0].checked = dict['enabled'];
    $('#deviceNameEntry').val(dict['name']);
    $('#deviceEntry').val(dict['proto'] + '://' + dict['device']);
    $('#lightSwitchDetectSwitch')[0].checked = dict['light_switch_detect'];
    $('#autoBrightnessSwitch')[0].checked = dict['auto_brightness'];
    
    $('#brightnessSlider').val(dict['brightness']);
    $('#contrastSlider').val(dict['contrast']);
    $('#saturationSlider').val(dict['saturation']);
    $('#hueSlider').val(dict['hue']);

    $('#resolutionSelect').html('');
    dict['available_resolutions'].forEach(function (resolution) {
        $('#resolutionSelect').append('<option value="' + resolution + '">' + resolution + '</option>');
    });
    $('#resolutionSelect').val(dict['resolution']);
    
    $('#rotationSelect').val(dict['rotation']);
    $('#framerateSlider').val(dict['framerate']);
    
    /* file storage */
    $('#storageDeviceSelect').val(dict['storage_device']);
    $('#networkServerEntry').val(dict['network_server']);
    $('#networkShareNameEntry').val(dict['network_share_name']);
    $('#networkUsernameEntry').val(dict['network_username']);
    $('#networkPasswordEntry').val(dict['network_password']);
    $('#rootDirectoryEntry').val(dict['root_directory']);
    
    /* text overlay */
    $('#textOverlaySwitch')[0].checked = dict['text_overlay'];
    $('#leftTextSelect').val(dict['left_text']);
    $('#leftTextEntry').val(dict['custom_left_text']);
    $('#rightTextSelect').val(dict['right_text']);
    $('#rightTextEntry').val(dict['custom_right_text']);
    
    /* video streaming */
    $('#videoStreamingSwitch')[0].checked = dict['video_streaming'];
    $('#streamingPortEntry').val(dict['streaming_port']);
    $('#streamingFramerateSlider').val(dict['streaming_framerate']);
    $('#streamingQualitySlider').val(dict['streaming_quality']);
    $('#streamingMotion')[0].checked = dict['streaming_motion'];
    
    /* still images */
    $('#stillImagesSwitch')[0].checked = dict['still_images'];
    $('#imageFileNameEntry').val(dict['image_file_name']);
    $('#imageQualitySlider').val(dict['image_quality']);
    $('#captureModeSelect').val(dict['capture_mode']);
    $('#snapshotIntervalEntry').val(dict['snapshot_interval']);
    $('#preserveImagesSelect').val(dict['preserve_images']);
    
    /* motion movies */
    $('#motionMoviesSwitch')[0].checked = dict['motion_movies'];
    $('#movieFileNameEntry').val(dict['movie_file_name']);
    $('#movieQualitySlider').val(dict['movie_quality']);
    $('#preserveMoviesSelect').val(dict['preserve_movies']);
    
    /* motion detection */
    $('#showFrameChangesSwitch')[0].checked = dict['show_frame_changes'];
    $('#frameChangeThresholdSlider').val(dict['frame_change_threshold']);
    $('#autoNoiseDetectSwitch')[0].checked = dict['auto_noise_detect'];
    $('#noiseLevelSlider').val(dict['noise_level']);
    $('#gapEntry').val(dict['gap']);
    $('#preCaptureEntry').val(dict['pre_capture']);
    $('#postCaptureEntry').val(dict['post_capture']);
    
    /* motion notifications */
    $('#motionNotificationsSwitch')[0].checked = dict['motion_notifications'];
    $('#emailAddressesEntry').val(dict['motion_notifications_emails']);
    
    /* working schedule */
    $('#workingScheduleSwitch')[0].checked = dict['working_schedule'];
    $('#mondayFrom').val(dict['monday_from']);
    $('#mondayTo').val(dict['monday_to']);
    $('#tuesdayFrom').val(dict['tuesday_from']);
    $('#tuesdayTo').val(dict['tuesday_to']);
    $('#wednesdayFrom').val(dict['wednesday_from']);
    $('#wednesdayTo').val(dict['wednesday_to']);
    $('#thursdayFrom').val(dict['thursday_from']);
    $('#thursdayTo').val(dict['thursday_to']);
    $('#fridayFrom').val(dict['friday_from']);
    $('#fridayTo').val(dict['friday_to']);
    $('#saturdayFrom').val(dict['saturday_from']);
    $('#saturdayTo').val(dict['saturday_to']);
    $('#sundayFrom').val(dict['sunday_from']);
    $('#sundayTo').val(dict['sunday_to']);
    
    updateConfigUi();
}

    
    /* apply button */

function showApply() {
    if (!$('div.settings-container').is(':visible')) {
        return; /* settings panel is not open */
    }

    var applyButton = $('#applyButton');
    
    applyButton.html('Apply');
    applyButton.css('display', 'inline-block');
    applyButton.animate({'opacity': '1'}, 100);
    applyButton.removeClass('progress');
}

function showProgress() {
    if (!$('div.settings-container').is(':visible')) {
        return; /* settings panel is not open */
    }

    var applyButton = $('#applyButton');
    
    if (applyButton.hasClass('progress')) {
        return; /* progress already visible */
    }
    
    applyButton.html('<img class="apply-progress" src="' + staticUrl + 'img/apply-progress.gif">');
    applyButton.css('display', 'inline-block');
    applyButton.animate({'opacity': '1'}, 100);
    applyButton.addClass('progress');   
    
    $('div.camera-progress').css('opacity', '0.5');
    
    refreshDisabled++;
}

function hideApply() {
    if (!$('div.settings-container').is(':visible')) {
        return; /* settings panel is not open */
    }

    var applyButton = $('#applyButton');
    
    applyButton.animate({'opacity': '0'}, 100, function () {
        applyButton.removeClass('progress');
        applyButton.css('display', 'none');
    });
}

function endProgress() {
    if (Object.keys(pushConfigs).length === 0) {
        hideApply();
    }
    else {
        showApply();
    }
    
    $('div.camera-progress').css('opacity', '0');
    
    refreshDisabled--;
}

function isProgress() {
    var applyButton = $('#applyButton');
    
    return applyButton.hasClass('progress');
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
    
    showProgress();
    
    ajax('POST', '/config/0/set/', pushConfigs, function (data) {
        if (data == null || data.error) {
            endProgress();
            showErrorMessage(data && data.error);
            return;
        }
        
        /* update the camera name in the device select */
        Object.keys(pushConfigs).forEach(function (key) {
            var config = pushConfigs[key];
            if (config.key !== 'main') {
                $('#videoDeviceSelect').find('option[value=' + key + ']').html(config.name);
            }
        });

        pushConfigs = {};
        endProgress();
        
        recreateCameraFrames();
    });
}

function doRemCamera() {
    var cameraId = $('#videoDeviceSelect').val();
    if (cameraId == null || cameraId === 'add') {
        runAlertDialog('No camera to remove!');
        return;
    }

    var deviceName = $('#videoDeviceSelect').find('option[value=' + cameraId + ']').text();
    
    runConfirmDialog('Remove device ' + deviceName + '?', function () {
        showProgress();
        ajax('POST', '/config/' + cameraId + '/rem/', null, function (data) {
            if (data == null || data.error) {
                endProgress();
                showErrorMessage(data && data.error);
                return;
            }
            
            endProgress();
            fetchCurrentConfig();
        });
    });
}


    /* fetch & push */

function fetchCurrentConfig() {
    function fetchCameraList() {
        /* fetch the camera list */
        ajax('GET', '/config/list/', null, function (data) {
            if (data == null || data.error) {
                showErrorMessage(data && data.error);
                data = {cameras: []};
            }
            
            var i, cameras = data.cameras;
            
            if (user === 'admin') {
                var videoDeviceSelect = $('#videoDeviceSelect');
                videoDeviceSelect.html('');
                for (i = 0; i < cameras.length; i++) {
                    var camera = cameras[i];
                    videoDeviceSelect.append('<option value="' + camera['id'] + '">' + camera['name'] + '</option>');
                }
                videoDeviceSelect.append('<option value="add">add camera...</option>');
                
                if (cameras.length > 0) {
                    videoDeviceSelect[0].selectedIndex = 0;
                    fetchCurrentCameraConfig();
                }
                else {
                    videoDeviceSelect[0].selectedIndex = -1;
                }
            
                updateConfigUi();
            }
            
            recreateCameraFrames(cameras);
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

function fetchCurrentCameraConfig() {
    var cameraId = $('#videoDeviceSelect').val();
    if (cameraId != null) {
        ajax('GET', '/config/' + cameraId + '/get/', null, function (data) {
            if (data == null || data.error) {
                showErrorMessage(data && data.error);
                return;
            }
            
            dict2CameraUi(data);
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
    var cameraId = $('#videoDeviceSelect').val();

    pushConfigs[cameraId] = cameraConfig;
    if (!isApplyVisible()) {
        showApply();
    }
}

function pushPreview() {
    var cameraId = $('#videoDeviceSelect').val();
    var brightness = $('#brightnessSlider').val();
    var contrast= $('#contrastSlider').val();
    var saturation = $('#saturationSlider').val();
    var hue = $('#hueSlider').val();
    
    var data = {};
    
    if (brightness !== '') {
        data.brightness = brightness;
    }
    
    if (contrast !== '') {
        data.contrast = contrast;
    }
    
    if (saturation !== '') {
        data.saturation = saturation;
    }
    
    if (hue !== '') {
        data.hue = hue;
    }
    
    refreshDisabled++;
    
    ajax('POST', '/config/' + cameraId + '/set_preview/', data, function (data) {
        refreshDisabled--;
        
        if (data == null || data.error) {
            showErrorMessage(data && data.error);
            return;
        }
    });
}


    /* dialogs */

function runAlertDialog(message) {
    runModalDialog({title: message, buttons: 'ok'});
}

function runConfirmDialog(message, onYes) {
    runModalDialog({title: message, buttons: 'yesno', onYes: onYes});
}

function runAddCameraDialog() {
    var content = 
            $('<table class="add-camera-dialog">' +
                '<tr>' +
                    '<td class="dialog-item-label"><span class="dialog-item-label">Device</span></td>' +
                    '<td class="dialog-item-value"><select class="styled" id="deviceSelect"></select></td>' +
                    '<td><span class="help-mark" title="the device you wish to add to motionEye">?</span></td>' +
                '</tr>' +
                '<tr class="remote">' +
                    '<td class="dialog-item-label"><span class="dialog-item-label">Host</span></td>' +
                    '<td class="dialog-item-value"><input type="text" class="styled" id="hostEntry" placeholder="e.g. 192.168.1.2"></td>' +
                    '<td><span class="help-mark" title="the remote motionEye host (e.g. 192.168.1.2)">?</span></td>' +
                '</tr>' +
                '<tr class="remote">' +
                    '<td class="dialog-item-label"><span class="dialog-item-label">Port</span></td>' +
                    '<td class="dialog-item-value"><input type="text" class="styled" id="portEntry" placeholder="e.g. 80"></td>' +
                    '<td><span class="help-mark" title="the remote motionEye port (e.g. 80)">?</span></td>' +
                '</tr>' +
                '<tr class="remote">' +
                    '<td class="dialog-item-label"><span class="dialog-item-label">Username</span></td>' +
                    '<td class="dialog-item-value"><input type="text" class="styled" id="usernameEntry" placeholder="username..."></td>' +
                    '<td><span class="help-mark" title="the remote administrator\'s username">?</span></td>' +
                '</tr>' +
                '<tr class="remote">' +
                    '<td class="dialog-item-label"><span class="dialog-item-label">Password</span></td>' +
                    '<td class="dialog-item-value"><input type="password" class="styled" id="passwordEntry" placeholder="password..."></td>' +
                    '<td><span class="help-mark" title="the remote administrator\'s password">?</span></td>' +
                '</tr>' +
                '<tr class="remote">' +
                    '<td class="dialog-item-label"><span class="dialog-item-label">Camera</span></td>' +
                    '<td class="dialog-item-value"><select class="styled" id="cameraSelect"></select></td>' +
                    '<td><span class="help-mark" title="the remote camera you wish to add to motionEye">?</span></td>' +
                '</tr>' +
            '</table>');
    
    /* collect ui widgets */
    var deviceSelect = content.find('#deviceSelect');
    var hostEntry = content.find('#hostEntry');
    var portEntry = content.find('#portEntry');
    var usernameEntry = content.find('#usernameEntry');
    var passwordEntry = content.find('#passwordEntry');
    var cameraSelect = content.find('#cameraSelect');
    
    /* make validators */
    makeTextValidator(hostEntry, true);
    makeNumberValidator(portEntry, 1, 65535, false, false, true);
    makeTextValidator(usernameEntry, true);
    makeTextValidator(deviceSelect, true);
    makeComboValidator(cameraSelect, true);
    
    /* ui interaction */
    content.find('tr.remote').css('display', 'none');
    
    function updateUi() {
        if (deviceSelect.val() === 'remote') {
            content.find('tr.remote').css('display', 'table-row');
        }
        else {
            content.find('tr.remote').css('display', 'none');
        }
        
        updateModalDialogPosition();
        cameraSelect.html('');

        /* re-validate all the validators */
        content.find('.validator').each(function () {
            this.validate();
        });
        
        if (uiValid() && deviceSelect.val() == 'remote') {
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
            query = query.not('#cameraSelect');
        }
        query.each(function () {
            if (this.invalid) {
                valid = false;
                return false;
            }
        });
        
        return valid;
    }
    
    function fetchRemoteCameras() {
        var progress = $('<div style="text-align: center; margin: 2px;"><img src="' + staticUrl + 'img/small-progress.gif"></div>');
        
        cameraSelect.hide();
        cameraSelect.before(progress);
        cameraSelect.parent().find('div').remove(); /* remove any previous progress div */
        
        var data = {
            host: hostEntry.val(),
            port: portEntry.val(),
            username: usernameEntry.val(),
            password: passwordEntry.val()
        };
        
        ajax('GET', '/config/list/', data, function (data) {
            if (data == null || data.error) {
                progress.remove();
                showErrorMessage(data && data.error);
                return;
            }
            
            cameraSelect.html('');
            progress.remove();
            
            if (data.error || !data.cameras) {
                return;
            }

            data.cameras.forEach(function (info) {
                cameraSelect.append('<option value="' + info.id + '">' + info.name + '</option>');
            });
            
            cameraSelect.show();
        });
    }
    
    deviceSelect.change(updateUi);
    hostEntry.change(updateUi);
    portEntry.change(updateUi);
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
                deviceSelect.append('<option value="' + device.device + '">' + device.name + '</option>');
            }
        });
        
        deviceSelect.append('<option value="remote">Remote device...</option>');
        
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
                if (deviceSelect.val() == 'remote') {
                    data.proto = 'http';
                    data.host = hostEntry.val();
                    data.port = portEntry.val();
                    data.username = usernameEntry.val();
                    data.password = passwordEntry.val();
                    data.remote_camera_id = cameraSelect.val();
                }
                else {
                    data.proto = 'v4l2';
                    data.device = deviceSelect.val();
                }

                showProgress();
                ajax('POST', '/config/add/', data, function (data) {
                    if (data == null || data.error) {
                        endProgress();
                        showErrorMessage(data && data.error);
                        return;
                    }
                    
                    endProgress();
                    var addCameraOption = $('#videoDeviceSelect').find('option[value=add]');
                    addCameraOption.before('<option value="' + data.id + '">' + data.name + '</option>');
                    $('#videoDeviceSelect').val(data.id).change();
                    recreateCameraFrames();
                });
            }
        });
    });
}


    /* camera frames */

function addCameraFrameUi(cameraId, cameraName, framerate) {
    var cameraFrameDiv = $(
            '<div class="camera-frame">' +
                '<div class="camera-top-bar">' +
                    '<span class="camera-name"></span>' +
                    '<div class="camera-buttons">' +
                        '<div class="button camera-button mouse-effect configure" title="configure"></div>' +
                        '<div class="button camera-button mouse-effect close" title="close"></div>' +
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
    var closeButton = cameraFrameDiv.find('div.camera-button.close');
    var cameraPlaceholder = cameraFrameDiv.find('div.camera-placeholder');
    var cameraProgress = cameraFrameDiv.find('div.camera-progress');
    var cameraImg = cameraFrameDiv.find('img.camera');
    var progressImg = cameraFrameDiv.find('img.camera-progress');
    
    /* no camera buttons if not admin */
    if (user !== 'admin') {
        configureButton.hide();
        closeButton.hide();
    }
    
    cameraFrameDiv.attr('id', 'camera' + cameraId);
    cameraFrameDiv[0].framerate = framerate;
    cameraFrameDiv[0].refreshDivider = 0;
    nameSpan.html(cameraName);
    progressImg.attr('src', staticUrl + 'img/camera-progress.gif');
    
    /* insert the new camera frame at the right position,
     * with respect to the camera id */
    var pageContainer = $('div.page-container');
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

    closeButton.click(function () {
        doCloseCamera(cameraId);
    });
    
    /* error and load handlers */
    cameraImg.error(function () {
        this.error = true;
        cameraImg.addClass('error');
        cameraImg.height(Math.round(cameraImg.width() * 0.75));
        cameraPlaceholder.css('opacity', 1);
    });
    cameraImg.load(function () {
        this.error = false;
        cameraImg.removeClass('error');
        cameraImg.css('height', '');
        cameraPlaceholder.css('opacity', 0);
        cameraProgress.css('opacity', 0);
    });
    
    cameraImg.error();
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
        var i, camera, cameraId;
        
        /* remove everything that is not a camera frame from the page */
        pageContainer.children().not('div.camera-frame').remove();
        
        /* remove no longer existing camera frames */
        var addedCameraFrames = pageContainer.find('div.camera-frame');
        for (i = 0; i < addedCameraFrames.length; i++) {
            cameraId = parseInt(addedCameraFrames[i].id.substring(6));
            if (cameras.filter(function (camera) {return camera.id === cameraId;}).length === 0) {
                remCameraFrameUi(cameraId);
            }
        }
        
        /* add new camera frames and update existing camera params */
        for (i = 0; i < cameras.length; i++) {
            camera = cameras[i];
            var cameraFrame = pageContainer.find('div.camera-frame#camera' + camera.id);
            if (cameraFrame.length === 0) { /* not existing, add a new one */
                addCameraFrameUi(camera.id, camera.name, camera.streaming_framerate);
            }
            else { /* existing, update params */
                cameraFrame[0].framerate = camera.streaming_framerate;
            }
        }
        
        if ($('#videoDeviceSelect').find('option').length < 2 && user === 'admin') {
            /* invite the user to add a camera */
            var addCameraLink = $('<div style="text-align: center; margin-top: 30px;">' + 
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
    openSettings(cameraId);
}

function doCloseCamera(cameraId) {
    remCameraFrameUi(cameraId);
    showProgress();
    ajax('GET', '/config/' + cameraId + '/get/', null, function (data) {
        if (data == null || data.error) {
            endProgress();
            showErrorMessage(data && data.error);
            return;
        }
        
        data['enabled'] = false;
        ajax('POST', '/config/' + cameraId + '/set/', data, function (data) {
            if (data == null || data.error) {
                showErrorMessage(data && data.error);
                return;
            }
            
            endProgress();
            
            /* if the current camera in the settings panel is the closed camera,
             * we refresh its settings and update the UI */
            if ($('#videoDeviceSelect').val() === '' + cameraId) {
                fetchCurrentCameraConfig();
            }
        });
    });
}

function refreshCameraFrames() {
    if (refreshDisabled) {
        /* camera refreshing disabled, retry later */
        
        setTimeout(refreshCameraFrames, 1000);

        return;
    }
    
    function refreshCameraFrame(cameraId, img) {
        img.src = '/snapshot/' + cameraId + '/current/?_=' + new Date().getTime();
    }
    
    var cameraFrames = $('div.page-container').find('div.camera-frame');
    cameraFrames.each(function () {
        /* limit the refresh rate to 10 fps */
        var count = Math.max(1, 10 / this.framerate);
        var img = $(this).find('img.camera')[0];
        
        if (img.error) {
            /* in case of error, decrease the refresh rate to 1 fps */
            count = 10;
        }
        
        if (this.refreshDivider < count) {
            this.refreshDivider++;
        }
        else {
            var cameraId = this.id.substring(6);
            refreshCameraFrame(cameraId, img);
            
            this.refreshDivider = 0;
        }
    });
    
    setTimeout(refreshCameraFrames, 100);
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
    
    /* prevent scroll events on settings div from propagating TODO this does not work */
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
    fetchCurrentConfig();
    refreshCameraFrames();
});
