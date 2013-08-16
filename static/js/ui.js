
function makeCheckBox($input) {
    var mainDiv = $('<div class="check-box"></div>');
    var buttonDiv = $('<div class="check-box-button"></div>');
    var text = $('<span class="check-box-text"><span>');
    
    function setOn() {
        text.html('ON');
        mainDiv.addClass('on');
    }
    
    function setOff() {
        text.html('OFF');
        mainDiv.removeClass('on');
    }
    
    buttonDiv.append(text);
    mainDiv.append(buttonDiv);
    
    /* transfer the CSS classes */
    mainDiv[0].className += ' ' + $input[0].className;
    
    /* add the element */
    $input.after(mainDiv);
    
    /* add event handers */
    $input.change(function () {
        if (this.checked) {
            setOn();
        }
        else {
            setOff();
        }
    }).change();
    
    mainDiv.click(function () {
        $input[0].checked = !$input[0].checked;
        $input.change();
    });
    
    /* make the element focusable */
    mainDiv[0].tabIndex = 0;
    
    /* handle the key events */
    mainDiv.keydown(function (e) {
        if (e.which === 13 || e.which === 32) {
            $input[0].checked = !$input[0].checked;
            $input.change();
            
            return false;
        }
    });
    
    return mainDiv;
}

function makeSlider($input, minVal, maxVal, snapMode, ticks, ticksNumber, decimals, unit) {
    unit = unit || '';
    
    var slider = $('<div class="slider"></div>');
    
    var labels = $('<div class="slider-labels"></div>');
    slider.append(labels);
    
    var bar = $('<div class="slider-bar"></div>');
    slider.append(bar);
    
    bar.append('<div class="slider-bar-inside"></div>');
    
    var cursor = $('<div class="slider-cursor"></div>');
    bar.append(cursor);
    
    function bestPos(pos) {
        if (pos < 0) {
            pos = 0;
        }
        if (pos > 100) {
            pos = 100;
        }
        
        if (snapMode > 0) {
            var minDif = Infinity;
            var bestPos = null;
            for (var i = 0; i < ticks.length; i++) {
                var tick = ticks[i];
                var p = valToPos(tick.value);
                var dif = Math.abs(p - pos);
                if ((dif < minDif) && (snapMode == 1 || dif < slider.width() / 65)) {
                    minDif = dif;
                    bestPos = p;
                }
            }
            
            if (bestPos != null) {
                pos = bestPos;
            }
        }
        
        return pos;
    }
    
    function getPos() {
        return parseInt(cursor.css('left'));
    }
    
    function valToPos(val) {
        return (val - minVal) * 100 / (maxVal - minVal);
    }
    
    function posToVal(pos) {
        return minVal + pos * (maxVal - minVal) / 100;
    }
    
    function sliderChange(val, percent) {
        $input.val(val.toFixed(decimals));
        slider.attr('title', '' + val.toFixed(decimals) + unit);
    }
    
    function bodyMouseMove(e) {
        if (bar[0]._mouseDown) {
            var offset = bar.offset();
            var pos = e.pageX - offset.left - 5;
            pos = pos / slider.width() * 100;
            pos = bestPos(pos);
            var val = posToVal(pos);
            
            cursor.css('left', pos + '%');
            sliderChange(val, pos / 100);
        }
    }
    
    function bodyMouseUp(e) {
        bar[0]._mouseDown = false;

        $('body').unbind('mousemove', bodyMouseMove);
        $('body').unbind('mouseup', bodyMouseUp);
    }
    
    bar.mousedown(function (e) {
        if (e.which > 1) {
            return;
        }
        
        this._mouseDown = true;
        bodyMouseMove(e);

        $('body').mousemove(bodyMouseMove);
        $('body').mouseup(bodyMouseUp);
        
        slider.focus();
        
        return false;
    });
    
    /* ticks */
    var i;
    if (ticks == null) {
        if (ticksNumber == null) {
            ticksNumber = 11; 
        }
        ticks = [];
        for (i = 0; i < ticksNumber; i++) {
            var val = minVal + i * (maxVal - minVal) / (ticksNumber - 1);
            var valStr;
            if (Math.round(val) == val) {
                valStr = '' + val;
            }
            else {
                valStr = val.toFixed(decimals);
            }
            ticks.push({value: val, label: valStr + unit});
        }
    }
    
    for (i = 0; i < ticks.length; i++) {
        var tick = ticks[i];
        var pos = valToPos(tick.value);
        var span = $('<span class="slider-label" style="left: -9999px;">' + tick.label + '</span>');
        
        labels.append(span);
        span.css('left', (pos - 10) + '%');
    }
    
    function input2slider() {
        var value = parseFloat($input.val());
        if (isNaN(value)) {
            value = minVal;
        }
        
        var pos = valToPos(value);
        pos = bestPos(pos);
        cursor.css('left', pos + '%');
        slider.attr('title', '' + $input.val() + unit);
    }
    
    /* transfer the CSS classes */
    slider[0].className += ' ' + $input[0].className;
    
    /* handle input events */
    $input.change(input2slider).change();
    
    /* add the slider to the parent of the input */
    $input.after(slider);
    
    /* make the slider focusable */
    slider[0].tabIndex = 0;
    
    /* handle key events */
    slider.keydown(function (e) {
        switch (e.which) {
            // TODO
        }
    });
    
    return slider;
}

function makeNumberValidator($input, minVal, maxVal, floating, sign, required) {
    if (minVal == null) {
        minVal = -Infinity;
    }
    if (maxVal == null) {
        maxVal = Infinity;
    }
    if (floating == null) {
        floating = false;
    }
    if (sign == null) {
        sign = false;
    }
    if (required == null) {
        required = true;
    }
    
    function isValid(strVal) {
        if (strVal.length === 0 && !required) {
            return true;
        }
        
        var numVal = parseInt(strVal);
        if ('' + numVal != strVal) {
            return false;
        }
        
        if (numVal < minVal || numVal > maxVal) {
            return false;
        }
        
        if (!sign && numVal < 0) {
            return false;
        }
        
        return true;
    }
    
    var msg = '';
    if (!sign) {
        msg = 'enter a positive';
    }
    else {
        msg = 'enter a'
    }
    if (floating) {
        msg += ' number';
    }
    else {
        msg += ' integer number';
    }
    if (isFinite(minVal)) {
        if (isFinite(maxVal)) {
            msg += ' between ' + minVal + ' and ' + maxVal;
        }
        else {
            msg += ' greater than ' + minVal;
        }
    }
    else {
        if (isFinite(maxVal)) {
            msg += ' smaller than ' + maxVal;
        }
    }
    
    function validate() {
        var strVal = $input.val();
        if (isValid(strVal)) {
            $input.attr('title', '');
            $input.removeClass('error');
        }
        else {
            $input.attr('title', msg);
            $input.addClass('error');
        }
    }
    
    $input.keyup(validate);
    $input.change(validate).change();
}

function makeTimeValidator($input) {
    function isValid(strVal) {
        return strVal.match('^[0-2][0-9]:[0-5][0-9]$') != null;
    }
    
    var msg = 'enter a valid time in the following format: HH:MM';
    
    function validate() {
        var strVal = $input.val();
        if (isValid(strVal)) {
            $input.attr('title', '');
            $input.removeClass('error');
        }
        else {
            $input.attr('title', msg);
            $input.addClass('error');
        }
    }
    
    $input.keyup(validate);
    $input.change(validate).change();
    $input.timepicker({
        closeOnWindowScroll: true,
        selectOnBlur: true,
        timeFormat: 'H:i',
    });
}
