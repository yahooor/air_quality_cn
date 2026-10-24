/*
var now = new Date();
var later = new Date();
later.setTime(now.getTime() + 365 * 24 * 60 * 60 * 1000);
setCookie("timezone_offset", now.getTimezoneOffset() / 60, later);
*/

var timezone = "";

function Request(argname) 
{ 
	var url = document.location.href; 
	var arrStr = url.substring(url.indexOf("?")+1).split("&"); 
	//return arrStr; 
	for(var i =0;i<arrStr.length;i++) 
	{ 
		var loc = arrStr[i].indexOf(argname+"="); 
	
	if(loc!=-1) 
	{ 
		return arrStr[i].replace(argname+"=","").replace("?",""); 
		break; 
	} 
	
	} 
	return "";
}

function activeQRTab(qrType)
{
	$("#qrcode-modal .qrcode").css("display","none");
	$("#qrcode-modal .nav-tabs li").removeClass("active");
	
	//alert(".reading-box ." + readingType);
	$("#" + qrType + "-qrcode").css("display","block");
	$("#qrcode-" + qrType + "-tab").addClass("active");
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