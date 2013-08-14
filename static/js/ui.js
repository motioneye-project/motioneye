
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
    
    $input.parent().append(mainDiv);
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
    
    /* handle input events */
    $input.change(input2slider).change();
    
    /* add the slider to the parent of the input */
    $input.parent().append(slider);
    
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

//function makeComboBox($select) {
//    var container = $('<div class="combo-box-container"></div>');
//    var buttonDiv = $('<div class="combo-box"></div>');
//    var opened = false;
//    var fading = false;
//    var defaultCaption = null;
//    var searchStr = '';
//    
//    container.append(buttonDiv);
//
//    var captionSpan = $('<span></span>');
//    buttonDiv.append(captionSpan);
//    buttonDiv.css('text-align', 'left');
//    
//    var arrowSpan = $('<span class="combo-box-arrow">&#x25BC;</span>');
//    buttonDiv.append(arrowSpan);
//    
//    var itemContainer = $('<div class="combo-box-item-container"</div>');
//    container.append(itemContainer);
//    itemContainer.mousedown(function () {
//        return false;
//    });
//    
//    itemContainer[0].tabIndex = 0;
//    
//    var itemDivs = [];
//    var captions = {};
//    $select.find('option').each(function () {
//        var option = $(this);
//        var caption = option.html();
//        var value = option.val();
//        
//        if (value == '') {
//            defaultCaption = caption;
//        }
//        
//        var itemDiv = $('<div class="combo-box-item">' + caption + '<div>');
//        itemContainer.append(itemDiv);
//        
//        itemDiv.click(function () {
//            setSelectedValue(value);
//            close();
//        });
//        itemDiv.mouseover(function () {
//            selectItemDiv(itemDiv);
//        });
//        
//        itemDiv[0]._value = value;
//        
//        itemDivs.push(itemDiv);
//        captions[value] = caption;
//    });
//    
//    $select.after(container);
//    buttonDiv.width(itemContainer.width() - 12);
//    
//    $select.change(function () {
//        setSelectedValue($select.val(), true);
//    }).change();
//    
//    function setSelectedValue(value, skipSelect) {
//        var caption = captions[value];
//        if (caption == null) {
//            if (defaultCaption == null) {
//                return;
//            }
//            caption = defaultCaption;
//        }
//        captionSpan.html(caption);
//        if (!skipSelect) {
//            $select.val(value);
//        }
//        
//        var itemDiv = getItemDivByValue(value);
//        if (itemDiv) {
//            selectItemDiv(itemDiv);
//        }
//    }
//    
//    function handleKeyDown(e) {
//        if (e.which == 13) { /* enter */
//            var itemDiv = itemContainer.find('div.combo-box-item-selected');
//            if (!itemDiv.length) {
//                return;
//            }
//            
//            var value = getValueByItemDiv(itemDiv);
//            setSelectedValue(value);
//            close();
//        }
//        else if (e.which == 8) { /* backspace */
//            if (searchStr.length) {
//                searchStr = searchStr.substring(0, searchStr.length - 1);
//            }
//        }
//        else if (e.which == 27) { /* escape */
//            close();
//        }
//        else if (e.which == 38) { /* up */
//            selectPrev();
//            return false;
//        }
//        else if (e.which == 40) { /* down */
//            selectNext();
//            return false;
//        }
//    }
//    
//    function handleKeyPress(e) {
//        searchStr += String.fromCharCode(e.which).toLowerCase();
//        
//        itemContainer.find('div.combo-box-item').each(function () {
//            var itemDiv = $(this);
//            if (itemDiv.text().toLowerCase().startsWith(searchStr)) {
//                selectItemDiv(itemDiv, true);
//                return false;
//            }
//        });
//    }
//    
//    function getValueByItemDiv(itemDiv) {
//        return itemDiv[0]._value;
//    }
//    
//    function getItemDivByValue(value) {
//        for (var i = 0; i < itemDivs.length; i++) {
//            var itemDiv = itemDivs[i];
//            if (itemDiv[0]._value == value) {
//                return itemDiv;
//            }
//        }
//        
//        return null;
//    }
//    
//    function selectPrev() {
//        var prevItemDiv = null;
//        var itemDiv = itemContainer.find('div.combo-box-item-selected');
//        if (!itemDiv.length) {
//            prevItemDiv = itemDivs.slice(-1)[0];
//        }
//        else {
//            for (var i = 0; i < itemDivs.length; i++) {
//                if (i > 0 && itemDiv[0] == itemDivs[i][0]) {
//                    prevItemDiv = itemDivs[i - 1];
//                    break;
//                }
//            }
//        }
//        
//        if (prevItemDiv) {
//            selectItemDiv(prevItemDiv, true);
//        }
//        
//        searchStr = '';
//    }
//    
//    function selectNext() {
//        var nextItemDiv = null;
//        var itemDiv = itemContainer.find('div.combo-box-item-selected');
//        if (!itemDiv.length) {
//            nextItemDiv = itemDivs[0];
//        }
//        else {
//            for (var i = 0; i < itemDivs.length; i++) {
//                if (i < itemDivs.length - 1 && itemDiv[0] == itemDivs[i][0]) {
//                    nextItemDiv = itemDivs[i + 1];
//                    break;
//                }
//            }
//        }
//        
//        if (nextItemDiv) {
//            selectItemDiv(nextItemDiv, true);
//        }
//        
//        searchStr = '';
//    }
//    
//    function selectItemDiv(itemDiv, scroll) {
//        var oldItemDiv = itemContainer.find('div.combo-box-item-selected');
//        if (oldItemDiv.length == 0 || oldItemDiv[0] !== itemDiv[0]) {
//            oldItemDiv.removeClass('combo-box-item-selected');
//            itemDiv.addClass('combo-box-item-selected');
//        }
//        
//        if (scroll) {
//            var scrollTop = itemDiv.offset().top - itemContainer.offset().top + itemContainer.scrollTop();
//            itemContainer.scrollTop(scrollTop);
//        }
//    }
//    
//    function open() {
//        buttonDiv.unlock();
//        buttonDiv.setActive();
//        buttonDiv.lock();
//        opened = true;
//        itemContainer.css('opacity', '0');
//        itemContainer.css('left', '0px');
//        fading = true;
//        itemContainer.animate({'opacity': '1'}, Reshaped.Forms.ANIM_DELAY, function () {
//            fading = false;
//        });
//        //arrowSpan.html('&#x25B2;');
//        
//        $('html').mousedown(close);
//        $('html').keydown(handleKeyDown);
//        $('html').keypress(handleKeyPress);
//        
//        itemContainer.focus();
//        searchStr = '';
//
//        var itemDiv = getItemDivByValue(select.val());
//        if (itemDiv) {
//            selectItemDiv(itemDiv, true);
//        }
//    }
//    
//    function close() {
//        buttonDiv.unlock();
//        buttonDiv.setNormal();
//        //arrowSpan.html('&#x25BC;');
//        opened = false;
//        fading = true;
//        itemContainer.animate({'opacity': '0'}, Reshaped.Forms.ANIM_DELAY, function () {
//            itemContainer.css('left', '-9999px');
//            fading = false;
//        });
//        
//        $('html').unbind('mousedown', close);
//        $('html').unbind('keydown', handleKeyDown);
//        $('html').unbind('keypress', handleKeyPress);
//        searchStr = '';
//    }
//    
//    buttonDiv.click(function () {
//        if (fading) {
//            return;
//        }
//        
//        if (opened) {
//            close();
//        }
//        else {
//            open();
//        }
//        
//        return false;
//    });
//    
//    return container;
//}
