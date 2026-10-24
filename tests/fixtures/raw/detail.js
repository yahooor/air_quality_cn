var map;
var reqParamData;
var historyData;
var markers = new Array();
var temperatureType = "";
var temperC = "";
var mapPolMapping = {};
var mapData;
var mapSelectedKind;
var isNearbyLoaded = false;


function initControls()
{
	$("#search-ac").autocomplete({
	  	source: function(request, response) {
	        $.ajax({
	            url: baseURL + "data/search_places",
	            dataType: "json",
	            data: {
		            term: request.term,
	                lang: langCode
	            },
	            success: function(data) {
	                response(data);
	            }
	        });
	    },
		minLength: 2,
		select: function(event, ui){
			if(ui.item.type == "continent")
			{
				window.location.href = baseURL + "continent/" + ui.item.url_key + "/" + ui.item.place_id + "?lang=" + langCode + "&standard=" + standard;
			}
			else if(ui.item.type == "country")
			{
				window.location.href = baseURL + ui.item.url_key + "/" + ui.item.place_id + "?lang=" + langCode + "&standard=" + standard;
			}
			else
			{
				window.location.href = baseURL + "place/" + ui.item.url_key + "/" + ui.item.place_id + "?lang=" + langCode + "&standard=" + standard;
			}
			
		}
	}).autocomplete( "instance" )._renderItem = function( ul, item ) {
	  return $( "<li>" )
	    .append( "<div><h4>" + item.name + "</h4><span>" + item.description + "</span></div>" )
	    .appendTo( ul );
	};
	
	$("#search-ac-nav").autocomplete({
	  	source: function(request, response) {
	        $.ajax({
	            url: baseURL + "data/search_places",
	            dataType: "json",
	            data: {
		            term: request.term,
	                lang: langCode
	            },
	            success: function(data) {
	                response(data);
	            }
	        });
	    },
		minLength: 2,
		select: function(event, ui){
			if(ui.item.type == "continent")
			{
				window.location.href = baseURL + "continent/" + ui.item.url_key + "/" + ui.item.place_id + "?lang=" + langCode + "&standard=" + standard;
			}
			else if(ui.item.type == "country")
			{
				window.location.href = baseURL + ui.item.url_key + "/" + ui.item.place_id + "?lang=" + langCode + "&standard=" + standard;
			}
			else
			{
				window.location.href = baseURL + "place/" + ui.item.url_key + "/" + ui.item.place_id + "?lang=" + langCode + "&standard=" + standard;
			}
			
		}
	}).autocomplete( "instance" )._renderItem = function( ul, item ) {
	  return $( "<li>" )
	    .append( "<div><h4>" + item.name + "</h4><span>" + item.description + "</span></div>" )
	    .appendTo( ul );
	};
	
	
	$('#temperature-dropdown li').click(function(e){
		//e.preventDefault();
		var selectedValue = $(this).attr("value");
		var selectedText = $(this).text();
		$(this).parents(".input-group-btn").find('.btn .text').text(selectedText);
		
		if(selectedValue == "C")
		{
			//alert("C");
			$(".forecast-box .temp_c").attr("style", "display:block");
			$(".forecast-box .temp_f").attr("style", "display:none");
			$(".weather-box").find('.temperature').text(curWeatherData.temp_c + selectedText);
		}
		else
		{
			//alert("F");
			$(".forecast-box .temp_f").attr("style", "display:block");
			$(".forecast-box .temp_c").attr("style", "display:none");
			$(".weather-box").find('.temperature').text(curWeatherData.temp_f + selectedText);
		}
	});
	
	$('#forecast-interval-dropdown li').click(function(e){
		//e.preventDefault();
		var selectedValue = $(this).attr("value");
		var selectedText = $(this).text();
		$(this).parents(".input-group-btn").find('.btn .text').text(selectedText);
		
		if(selectedValue == "daily")
		{
			$(".daily-forecast-scroll").attr("style", "display:block");
			$(".hourly-forecast-scroll").attr("style", "display:none");
		}
		else
		{
			$(".hourly-forecast-scroll").attr("style", "display:block");
			$(".daily-forecast-scroll").attr("style", "display:none");
		}
	});
	
	$('#history-interval-dropdown li').click(function(e){
		//e.preventDefault();
		var selectedValue = $(this).attr("value");
		var selectedText = $(this).text();
		$(this).parents(".input-group-btn").find('.btn .text').text(selectedText);
		
		historyTimeInterval = selectedValue;
		drawHistoryChart();
	});
	
	$('#history-kind-dropdown li').click(function(e){
		//e.preventDefault();
		var selectedValue = $(this).attr("value");
		var selectedText = $(this).text();
		$(this).parents(".input-group-btn").find('.btn .text').text(selectedText);
		
		historyKind = selectedValue;
		drawHistoryChart();
	});
	
	$('#standards-dropdown li').click(function(e){
		//e.preventDefault();
		var selectedValue = $(this).attr("value");
		var selectedText = $(this).text();
		$(this).parents(".input-group-btn").find('.btn .text').text(selectedText);
		
		window.location.href = baseURL + "place/" + urlKey + "/" + placeID + "?lang=" + langCode + "&standard=" + selectedValue;
	});
	
	$('#map-standards-dropdown li').click(function(e){
		//e.preventDefault();
		var selectedValue = $(this).attr("value");
		var selectedText = $(this).text();
		$(this).parents(".input-group-btn").find('.btn .text').text(selectedText);
		
		window.location.href = baseURL + "map?lang=" + langCode + "&standard=" + selectedValue;
	});
	
	$('#standard-nav-list li').click(function(e){
		//e.preventDefault();
		var selectedValue = $(this).attr("value");
		var selectedText = $(this).text();
		
		window.location.href = baseURL + "place/" + urlKey + "/" + placeID + "?lang=" + langCode + "&standard=" + selectedValue;
	});
	
	$('#standards-country-dropdown li').click(function(e){
		//e.preventDefault();
		var selectedValue = $(this).attr("value");
		var selectedText = $(this).text();
		$(this).parents(".input-group-btn").find('.btn .text').text(selectedText);
		
		window.location.href = baseURL + urlKey + "/" + placeID + "?lang=" + langCode + "&standard=" + selectedValue;
	});
	
	$(document).on("click", "#kind-dropdown li", function(e){ 
		//alert("1");
		//e.preventDefault();
		var selectedValue = $(this).attr("value");
		var selectedText = $(this).text();
		$(this).parents(".input-group-btn").find('.btn .text').text(selectedText);
		
		mapSelectedKind = selectedValue;
		drawMapMarkers();
	});
	
	$('#rank-dropdown li').click(function(e){
		var selectedValue = $(this).attr("value");
		var selectedText = $(this).text();
		$(this).parents(".input-group-btn").find('.btn .text').text(selectedText);
		
		drawRanking(selectedValue);
	});
	
	$('#rank-order-dropdown li').click(function(e){
		//e.preventDefault();
		var selectedValue = $(this).attr("value");
		var selectedText = $(this).text();
		$(this).parents(".input-group-btn").find('.btn .text').text(selectedText);
		
		rankingOrder = selectedValue;
		drawDetailRanking();
	});
	
	$('#rank-range-dropdown li').click(function(e){
		//e.preventDefault();
		var selectedValue = $(this).attr("value");
		var selectedText = $(this).text();
		$(this).parents(".input-group-btn").find('.btn .text').text(selectedText);
		
		rankingRange = selectedValue;
		drawDetailRanking();
	});
}

function drawHistoryChart(){
	
	$(".history-value-tag").hide();
    $.ajax({
	    type: 'POST',
	    url: baseURL + "data/get_history_data",
	    data: {"place_id": placeID, "kind": historyKind, "standard": standard, "interval": historyTimeInterval, "lang": langCode},
	    success: function(respData){
		    
		    if(respData.success)
		    {
			    $(".history-box .history-items").empty();
			    
			    historyData = respData.data.history[0].data;
			    //alert(historyData);
			    for(var i = 0; i < historyData.length; i++)
			    {
				    if(historyData[i].value == undefined && (i == historyData.length - 1 || i == historyData.length - 2)) continue;
				    			    
				    var chargeSpecialDateItem = $('<div class="history-item" style="left: ' + ((15 * i) + 0) + 'px;" id="item_' + i + '"><div class="history-item-bar" style="height:' + 160 * historyData[i].ratio + 'px; background:' + historyData[i].color + ';" id="item_' + i + '"></div></div>');
				    
				    chargeSpecialDateItem.mouseover(function(e){
						var curId = $(this).attr("id")
						var curNum = curId.substring(curId.indexOf("_") + 1,curId.length);
						//console.log(curNum);
						//console.log(e.pageX);
						//console.log($(this).offset().left - $(this).parent().offset().left);
						//console.log($(this).parent().parent().scrollLeft());
						
						//$(".history-value-tag").stop(true);
						$(".history-value-tag").show();
						
						var tagX = $(this).offset().left - $(this).parent().offset().left - $(this).parent().parent().scrollLeft();
						
						tagX = tagX * ($(this).parent().parent().width() - $(".history-value-tag").width()) / $(this).parent().parent().width();
						
						$(".history-value-tag").css("left", tagX + 20 + "px");
						var dataValue = historyData[curNum].value;
						if(dataValue == undefined) dataValue = "--";
						//alert(respData.data.history[0]);
						
						$(".history-value-tag").text(updateTimezone(historyData[curNum].time) + ", " + dataValue);
					});
					
					chargeSpecialDateItem.mouseout(function(){
						//$(".history-value-tag").stop(true);
						$(".history-value-tag").hide();
					});
				    
					$(".history-box .history-items").append(chargeSpecialDateItem);
				}
				
				$('.history-scroll').animate({
					scrollLeft: $('.history-scroll')[0].scrollWidth
				}, 800);
		    }
		},
	    dataType: 'json'
	});
}

function updateTimezone(datetime)
{
    return moment.utc(datetime).local().format('YYYY-MM-DD HH:mm');
}

function drawRanking(order){
    $.ajax({
	    type: 'POST',
	    url: baseURL + "data/get_ranking",
	    data: {"place_id": rankingPlaceID, "standard": standard, "order": order, "lang": langCode},
	    success: function(respData){
		    
		    if(respData.success && respData.data !== null)
		    {
			    $(".detail-side-ranking .side-block-content").empty();
			    
			    var rankingData = respData.data.rank;
			    //alert(rankingData.length);
			    for(var i = 0; i < rankingData.length; i++)
			    {   
				    $(".detail-side-ranking .side-block-content").append("<a href='" + baseURL + "place/" + rankingData[i].place.url_key + "/" + rankingData[i].place.place_id + "?lang=" + langCode + "&standard=" + standard + "' target='_self' class='site-item'><div class='rank'>" + rankingData[i].ranking + "</div><div class='title'>" + rankingData[i].place.name + "</div><div class='value-wrap'><div class='value' style='background:" + rankingData[i].reading.color + ";'>" + rankingData[i].reading.value + "</div></div></a>");
				}
				
				if(rankingData.length != 0)
				{
					$(".detail-side-ranking").show();
				}
		    }
		},
	    dataType: 'json'
	});
}

function drawDetailRanking(){
    $.ajax({
	    type: 'POST',
	    url: baseURL + "data/get_ranking",
	    data: {"place_id": rankingPlaceID, "standard": standard, "order": rankingOrder, "lang": langCode, "range": rankingRange, "result_number": 100},
	    success: function(respData){
		    
		    if(respData.success)
		    {
			    $(".rank-box .main-block-content").empty();
			    
			    var rankingData = respData.data.rank;
			    //alert(rankingData.length);
			    for(var i = 0; i < rankingData.length; i++)
			    {   
				    $(".rank-box .main-block-content").append("<a href='" + baseURL + "place/" + rankingData[i].place.url_key + "/" + rankingData[i].place.place_id + "?lang=" + langCode + "&standard=" + standard + "' target='_self' class='site-item'><div class='rank'>" + rankingData[i].ranking + "</div><div class='title'>" + rankingData[i].place.name + "</div><div class='value-wrap'><div class='value' style='background:" + rankingData[i].reading.color + ";'>" + rankingData[i].reading.value + "</div></div></a>");
				}
				
				$(".rank-box .main-block-content").append("<div class='clr'></div>");
				
				if(rankingData.length != 0)
				{
					$(".rank-box").show();
				}
		    }
		},
	    dataType: 'json'
	});
}

function drawMajorRanking(order){
	
	var majorCities = "北京,天津,上海,重庆,石家庄,唐山,秦皇岛,邯郸,保定,承德,沧州,衡水,邢台,张家口,廊坊,太原,呼和浩特,沈阳,大连,长春,哈尔滨,南京,苏州,无锡,常州,扬州,镇江,南通,泰州,徐州,连云港,淮安,盐城,宿迁,杭州,宁波,湖州,嘉兴,绍兴,舟山,温州,金华,衢州,台州,丽水,合肥,福州,厦门,南昌,济南,青岛,郑州,武汉,长沙,广州,深圳,珠海,佛山,江门,东莞,中山,惠州,肇庆,南宁,海口,成都,贵阳,昆明,拉萨,西安,兰州,西宁,银川,乌鲁木齐";
	
    $.ajax({
	    type: 'POST',
	    url: baseURL + "data/get_ranking",
	    data: {"place_id": rankingPlaceID, "standard": standard, "order": order, "lang": langCode, "range": "2years", "result_number": 400},
	    success: function(respData){
		    
		    if(respData.success)
		    {
			    $(".detail-side-ranking .side-block-content").empty();
			    
			    var rankingData = respData.data.rank;
			    //alert(rankingData.length);
			    var count = 0;
			    for(var i = 0; i < rankingData.length; i++)
			    {
				    if(majorCities.indexOf(rankingData[i].place.name) == -1) continue;
				    
				    count++;
				    
				    $(".detail-side-ranking .side-block-content").append("<a href='" + baseURL + "place/" + rankingData[i].place.url_key + "/" + rankingData[i].place.place_id + "?lang=" + langCode + "&standard=" + standard + "' target='_self' class='site-item'><div class='rank'>" + count + "</div><div class='title'>" + rankingData[i].place.name + "</div><div class='value-wrap'><div class='value' style='background:" + rankingData[i].reading.color + ";'>" + rankingData[i].reading.value + "</div></div></a>");
				}
				
				if(rankingData.length != 0)
				{
					$(".detail-side-ranking").show();
				}
		    }
		},
	    dataType: 'json'
	});
}

function getMapData()
{
	reqParamData = {"center_lat": map.getCenter().lat, "center_lon": map.getCenter().lng, "span_lat": map.getBounds().getNorth() - map.getBounds().getSouth(), "span_lon": map.getBounds().getEast() - map.getBounds().getWest(), "standard": standard, "lang": langCode};
	
	mapPolMapping = {};
	
    $.ajax({
	    type: 'POST',
	    url: baseURL + "data/get_map_data",
	    data: reqParamData,
	    success: function(respData){
		    
		    if(respData.success)
		    {
				mapData = respData.data.map;
				
				respData.data.map.forEach(function(row){
					if(row.latest.readings !== undefined)
					{
						row.latest.readings.forEach(function(reading){
							mapPolMapping[reading.kind] = reading.name;
						});
					}
				});
				
				$("#kind-dropdown").find('.btn .text').empty();
				$("#kind-dropdown").find('.dropdown-menu').empty();
				
				//判断列表中是否有 mapSelectedKind
				for(var key in mapPolMapping){
					//console.log(mapSelectedKind + ", " + key);
					
					if(mapSelectedKind == key)
					{
						//console.log("same");
						$("#kind-dropdown").find('.btn .text').text(mapPolMapping[key]);
					}
					$("#kind-dropdown").find('.dropdown-menu').append("<li value='" + key + "'>" + mapPolMapping[key] + "</li>");
				}
				
				//如果都与 mapSelectedKind 不一致，则选第一个为 mapSelectedKind
				for(var key in mapPolMapping){
					if($("#kind-dropdown").find('.btn .text').text() == "")
					{
						//console.log("not same and set");
						mapSelectedKind = key;
						$("#kind-dropdown").find('.btn .text').text(mapPolMapping[key]);
					}
				}
				
				drawMapMarkers();
				$("#kind-dropdown").show();
				
		    };
		},
	    dataType: 'json'
	});
}

function getNearbyData(curLat, curLon)
{
    if(isNearbyLoaded) return;
    
	reqParamData = {"lat": curLat, "lon": curLon, "standard": standard, "lang": langCode};
	
	mapPolMapping = {};
	
    $.ajax({
	    type: 'POST',
	    url: baseURL + "data/get_nearby_data",
	    data: reqParamData,
	    success: function(respData){
		    
		    if(isNearbyLoaded) return;
		    var cardPlace;

		    //console.log(respData.data.nearby.length);
		    if(respData.data.nearby.length == 0) return;
		    if(respData.data.nearby.length >= 1) cardPlace = respData.data.nearby[0];
		    //if(respData.data.nearby.length >= 2) cardPlace = respData.data.nearby[0];
		    console.log(cardPlace);
		    
		    var topColsHTML = "";
		    var readingCount = -1;
		    cardPlace.latest.readings.forEach(function(reading){
    		    readingCount++;
    		    if(readingCount > 0 && readingCount < 4)
    		    {
        		    marginStyle = "";
        		    if(readingCount == 1) marginStyle = " margin-left: 0;";
                    topColsHTML = topColsHTML + "<div class='pol_item' style='border-color:"+ cardPlace.latest.readings[readingCount].color + ";" + marginStyle +"'><div class='pol_name'>" + cardPlace.latest.readings[readingCount].name + "</div><div class='pol_value'>" + cardPlace.latest.readings[readingCount].value + "</div></div>";
    		    }
            });
            
            var healthAdviceHTML = "";
            if(cardPlace.health_advice[0] !== undefined)
            {
                var hexColor = hexToRgb(cardPlace.health_advice[0].color);
                
                healthAdviceHTML = "<div class='health_advice_wrapper'><div class='health_advice_icon' style='background-image:url(\"css/images/health_advice/" + cardPlace.health_advice[0].icon + ".png\"); background-color: rgba(" + hexColor.r + ", " + hexColor.g + ", " + hexColor.b + ", 0.85);'></div><div class='health_advice_name'>" + cardPlace.health_advice[0].title + "</div><div class='health_advice_level'>" + cardPlace.health_advice[0].description + "</div></div>";
            }
            
            var weatherHTML = "";
            if(cardPlace.latest.weather !== undefined)
            {
                weatherHTML = "<div class='weather_wrapper'><div class='weather_icon' style='background-image:url(\"css/images/weather/weather_" + cardPlace.latest.weather.icon + "_light.png\");'><span class='weather_temp_value'>" + cardPlace.latest.weather.temp_c + "</span> ℃</div></div>";
            }
		    
		    $("#nearby_card").html("<div class='place_name'>" + cardPlace.place.name + "</div><div class='aqi_name'>" + cardPlace.latest.readings[0].name + "<span class='aqi_level'>" + cardPlace.latest.readings[0].level + "</span></div><div style='border-color:" + cardPlace.latest.readings[0].color + "' class='aqi_number'>" + cardPlace.latest.readings[0].value + "</div><div class='pols_wrapper'>" + topColsHTML + "<div class='clr'></div></div>" + healthAdviceHTML + weatherHTML + "<div class='clr'></div>");
		    //$("#nearby_card").css("display", "block");
		    $("#nearby_card").css("opacity", "1");
		    $("#nearby_card").css("bottom", "15px");
		    $("#nearby_card").click(function(){
                window.location.href = baseURL + "place/" + cardPlace.place.url_key + "/" + cardPlace.place.place_id + "?lang=" + langCode + "&standard=" + standard;
            });
		    isNearbyLoaded = true;
		},
	    dataType: 'json'
	});
}

function hexToRgb(hex) {
  var result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  return result ? {
    r: parseInt(result[1], 16),
    g: parseInt(result[2], 16),
    b: parseInt(result[3], 16)
  } : null;
}

function drawMapMarkers()
{
	removeAllMarkers();
	mapData.forEach(function(row){
					
		if(row.place !== undefined)
		{
			var placeData = row.place;
			var readingData;
			
			row.latest.readings.forEach(function(reading){
				if(reading.kind == mapSelectedKind){
					readingData = reading;
				}
			});
			
			if(readingData == undefined) return;
			
			var pos = new L.LatLng(placeData.lat,placeData.lon);
			
			var icon = L.divIcon({
				className: 'map-marker',
				iconSize:null,
				html:'<div class="marker" style="background:' + readingData.color + ';">'+readingData.value+'</div><div class="arrow" />'
			});
			
			var marker = L.marker(pos,{icon: icon, place_id: placeData.place_id, url_key: placeData.url_key	});
			marker.addTo(map).bindTooltip(placeData.name, {direction: "top"});
			marker.on('click', function(ev) {
    			 window.location.href = baseURL + "place/" + this.options.url_key + "/" + this.options.place_id + "?lang=" + langCode + "&standard=" + standard;
			});
			markers.push(marker);
			//console.log("add: " + j);
			//marker.bindTooltip("my tooltip text").openTooltip();
		}
	});
}

function activeReading(readingType)
{
	$(".reading-box div.pollutants").css("display","none");
	$(".reading-box div.allergens").css("display","none");
	$("#pollutants_link").removeClass("active");
	$("#allergens_link").removeClass("active");
	
	
	//alert(".reading-box ." + readingType);
	$(".reading-box div." + readingType).css("display","block");
	$("#" + readingType + "_link").addClass("active");
}

function removeAllMarkers() {
	var markersNum = markers.length;
	//console.log("start remove:" + markers.length);
	for(i = 0; i < markersNum; i++) {
		//alert(markers[i]);
		//markers[i].remove();
	    map.removeLayer(markers[0]);
	    markers.shift();
	    //console.log("remove: " + i);
	}
	//console.log("after remove:" + markers.length);
}

function changeLang(langCode)
{
    $.ajax({
	    type: 'POST',
	    url: baseURL + "config/change_lang",
	    data: {"lang": langCode, "standard": standard, "url": window.location.href},
	    success: function(respData){
		    //window.location.reload();
		    window.location.href = respData.url;
		},
	    dataType: 'json'
	});
}

function setCookie(c_name,value,expiredays){
	var exdate=new Date()
	exdate.setDate(exdate.getDate()+expiredays)
	document.cookie=c_name+ "=" +escape(value)+ ((expiredays==null) ? "" : ";expires="+exdate.toGMTString())
}

function getCookie(c_name){
	if (document.cookie.length>0){
		c_start=document.cookie.indexOf(c_name + "=")
		if (c_start!=-1){ 
			c_start=c_start + c_name.length+1 
			c_end=document.cookie.indexOf(";",c_start)
			if (c_end==-1) c_end=document.cookie.length
			return unescape(document.cookie.substring(c_start,c_end))
		} 
	}
	return ""
}