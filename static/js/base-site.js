

var noPushLock = 0;


    /* Ajax */

function ajax(method, url, data, callback) {
    var options = {
        type: method,
        url: url,
        data: data,
        cache: false,
        success: callback,
        failure: function (request, options, error) {
            alert('Request failed with code: ' + request.status);
            if (callback) {
                callback();
            }
        }
    };
    
    if (data && typeof data === 'object') {
        options['contentType'] = 'application/json';
        options['data'] = JSON.stringify(options['data']);
    }
    
    $.ajax(options);
}


    /* UI */

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
    $('#motionEyeSwitch').change(updateConfigUI);
    $('#showAdvancedSwitch').change(updateConfigUI);
    $('#storageDeviceSelect').change(updateConfigUI);
    $('#autoBrightnessSwitch').change(updateConfigUI);
    $('#leftTextSelect').change(updateConfigUI);
    $('#rightTextSelect').change(updateConfigUI);
    $('#captureModeSelect').change(updateConfigUI);
    $('#autoNoiseDetectSwitch').change(updateConfigUI);
    $('#videoDeviceSwitch').change(updateConfigUI);
    $('#textOverlaySwitch').change(updateConfigUI);
    $('#videoStreamingSwitch').change(updateConfigUI);
    $('#stillImagesSwitch').change(updateConfigUI);
    $('#motionMoviesSwitch').change(updateConfigUI);
    $('#motionNotificationsSwitch').change(updateConfigUI);
    $('#workingScheduleSwitch').change(updateConfigUI);
    
    /* fetch & push handlers */
    $('#videoDeviceSelect').change(fetchCameraConfig);
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
}

function updateConfigUI() {
    noPushLock++;
    
    var objs = $('tr.settings-item, div.advanced-setting, table.advanced-setting, div.settings-section-title, table.settings');
    
    function markHide() {
        this._hide = true;
    }
    
    function unmarkHide() {
        this._hide = false;
    }
    
    objs.each(unmarkHide);
    
    /* general enable switch */
    var motionEyeEnabled = $('#motionEyeSwitch').get(0).checked;
    if (!motionEyeEnabled) {
        objs.not($('#motionEyeSwitch').parents('div').get(0)).each(markHide);
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
    
    /* re-validate all the input validators */
    $('div.settings').find('input.number-validator, input.time-validator').each(function () {
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
    
    noPushLock--;
}

function mainUi2Dict() {
    return {
        '@enabled': $('#motionEyeSwitch')[0].checked,
        '@show_advanced': $('#showAdvancedSwitch')[0].checked,
        '@admin_username': $('#adminUsernameEntry').val(),
        '@admin_password': $('#adminPasswordEntry').val(),
        '@normal_username': $('#normalUsernameEntry').val(),
        '@normal_password': $('#normalPasswordEntry').val()
    };
}

function dict2MainUi(dict) {
    noPushLock++;
    
    $('#motionEyeSwitch')[0].checked = dict['@enabled'];
    $('#showAdvancedSwitch')[0].checked = dict['@show_advanced'];
    $('#adminUsernameEntry').val(dict['@admin_username']);
    $('#adminPasswordEntry').val(dict['@admin_password']);
    $('#normalUsernameEntry').val(dict['@normal_username']);
    $('#normalPasswordEntry').val(dict['@normal_password']);
    
    updateConfigUI();
    
    noPushLock--;
}

function cameraUi2Dict() {
    return {
        /* video device */
        'enabled': $('#videoDeviceSwitch')[0].checked,
        'name': $('#deviceNameEntry').val(),
        'device': $('#deviceEntry').val(),
        'light_switch_detect': $('#lightSwitchDetectSwitch')[0].checked,
        'auto_brightness': $('#autoBrightnessSwitch')[0].checked,
        'brightness': $('#brightnessSlider').val(),
        'contrast': $('#contrastSlider').val(),
        'saturation': $('#saturationSlider').val(),
        'hue': $('#hueSlider').val(),
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
}

function dict2CameraUi(dict) {
    noPushLock++;
    
    /* video device */
    $('#videoDeviceSwitch')[0].checked = dict['enabled'];
    $('#deviceNameEntry').val(dict['name']);
    $('#deviceEntry').val(dict['device']);
    $('#lightSwitchDetectSwitch')[0].checked = dict['light_switch_detect'];
    $('#autoBrightnessSwitch')[0].checked = dict['auto_brightness'];
    $('#brightnessSlider').val(dict['brightness']);
    $('#contrastSlider').val(dict['contrast']);
    $('#saturationSlider').val(dict['saturation']);
    $('#hueSlider').val(dict['hue']);
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
    
    updateConfigUI();
    
    noPushLock--;
}

function fetchCurrentConfig() {
    /* fetch the main configuration */
    ajax('GET', '/config/main/get/', null, function (data) {
        dict2MainUi(data);
    });
    
    /* fetch the camera list */
    ajax('GET', '/config/list/', null, function (data) {
        var i, cameras = data.cameras;
        var videoDeviceSelect = $('#videoDeviceSelect');
        videoDeviceSelect.html('');
        for (i = 0; i < cameras.length; i++) {
            var camera = cameras[i];
            videoDeviceSelect.append('<option value="' + camera['@id'] + '">' + camera['@name'] + '</option>');
        }
        
        if (cameras.length) {
            videoDeviceSelect[0].selectedIndex = 0;
            fetchCameraConfig();
        }
    });
}

function fetchCameraConfig() {
    var cameraId = $('#videoDeviceSelect').val();
    if (cameraId != null) {
        ajax('GET', '/config/' + cameraId + '/get/', null, function (data) {
            dict2CameraUi(data);
        });
    }
    else {
        dict2CameraUi({});
    }
}

function pushMainConfig() {
    if (noPushLock) {
        return;
    }
    
    noPushLock++;
    
    var mainConfig = mainUi2Dict();
    
    ajax('POST', '/config/main/set/', mainConfig, function () {
        noPushLock--;
    });
}

function pushCameraConfig() {
    if (noPushLock) {
        return;
    }
    
    noPushLock++;
    
    var cameraConfig = cameraUi2Dict();
    var cameraId = $('#videoDeviceSelect').val();
    
    ajax('POST', '/config/' + cameraId + '/set/', cameraConfig, function () {
        noPushLock--;
    });
}

$(document).ready(function () {
    /* open/close settings */
    $('img.settings-button').click(function () {
        if ($('div.settings').hasClass('open')) {
            $('div.settings').removeClass('open');
            $('div.page-container').removeClass('stretched');
            $('div.settings-top-bar').removeClass('open');
        }
        else {
            $('div.settings').addClass('open');
            $('div.page-container').addClass('stretched');
            $('div.settings-top-bar').addClass('open');
        }
    });
    
    /* prevent scroll events on settings div from propagating */
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
    updateConfigUI();
    fetchCurrentConfig();
});
