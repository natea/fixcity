var map, layer, select, select_vector, racks, bounds, selectControl;

if (jQuery.browser.msie) {
    jQuery(window).load(function () {
        onload();
    });
} else {
    jQuery(document).ready(function () {
        onload();
    });
}

function onload() {
    loadMap();
    updateFilterBehaviors();
}

var options = {
    projection: new OpenLayers.Projection("EPSG:900913"),
    displayProjection: new OpenLayers.Projection("EPSG:4326"),
    units: "m",
    numZoomLevels: 19,
    maxResolution: 156543.03390625,
    maxExtent: new OpenLayers.Bounds(-20037508.34, -20037508.34, 20037508.34, 20037508.34)
};

function loadMap() {
    map = new OpenLayers.Map('verify-map', options);

    var osm = new OpenLayers.Layer.WMS("OpenStreetMap", "http://maps.opengeo.org/geowebcache/service/wms", {
        layers: "openstreetmap",
        format: "image/png",
        bgcolor: '#A1BDC4'
    },
    {
        wrapDateLine: true
    });

    var style = new OpenLayers.Style({
        pointRadius: "8",
        externalGraphic: "${url}"
        },
        {
        context: {
            url: function(feature) {
                if (feature.attributes.verified) {
                    return "/site_media/img/rack-verified-icon.png";
                } else {
                    return "/site_media/img/rack-icon.png";
                }
            }
        }
        });
    var style = new OpenLayers.Style({
        pointRadius: "${radius}",
        externalGraphic: "${url}",
    },
    {
    context: {
      url: function(feature) {
        if (feature.cluster.length > 1) {
          var n = feature.cluster.length;
          for (var i = 0; i < n; i++) {
            if (feature.cluster[i].attributes.verified == null) {
              return "/site_media/img/rack-icon.png";
            }
          }
          return "/site_media/img/rack-verified-icon.png";
        } else if (feature.cluster[0].attributes.verified) {
          return "/site_media/img/rack-verified-icon.png";
        } else {
        return "/site_media/img/rack-icon.png";
        }
      },
      radius: function(feature) {
        return Math.min(feature.attributes.count, 8) + 5;
      }
    }
    });

    function loadRacks() {
        racks = new OpenLayers.Layer.Vector("Racks", {
            projection: map.displayProjection,
            strategies: [
              new OpenLayers.Strategy.Fixed(),
              new OpenLayers.Strategy.Cluster()
            ],
            protocol: new OpenLayers.Protocol.HTTP({
                url: "/rack/requested.kml",
                params: {},
                format: new OpenLayers.Format.KML()
            }),
            styleMap: new OpenLayers.StyleMap({
                "default": style,
                "select": {
                    fillColor: "#ff9e73",
                    strokeColor: "#80503b"
                }
            })
        });
        var featureSelected = function(feature) {
            //$('ul#racklist li').removeClass('selected').filter('#rack_' + feature.fid).addClass('selected');
          var cluster = feature.cluster;
          var firstFeature = cluster[0];
          // can potentially select multiple racks
          $('ul.home-list li').removeClass('selected');
          var homeList = $('ul.home-list');
          for (var i = 0; i < feature.cluster.length; i++) {
            homeList.find('#rack_' + feature.cluster[i].fid).addClass('selected');
          }

          //var popup = new FixcityPopup(null, feature.geometry.getBounds().getCenterLonLat(),
          //                             null, ('<div class="rack-info"><a href="/rack/' + feature.fid + '"><img src="' + ((feature.cluster[0].attributes.thumbnail != null) ? feature.cluster[0].attributes.thumbnail.value : '/site_media/img/default-rack.jpg') + '" width="50" /></a><h3><a href="/rack/' + feature.fid + '">' + feature.cluster[0].attributes.name + '</a></h3><h4>' + feature.cluster[0].attributes.address + '</h4>' + ((feature.cluster[0].attributes.verified == null) ? '' : '<h5><em>verified</em></h5>') + '</div>'),
          //                             {size: new OpenLayers.Size(1, 1), offset: new OpenLayers.Pixel(-40, 48)},
          //                             true, function() { selectControl.unselect(feature); });
          var cluster = feature.cluster;
          var firstFeature = cluster[0];
          var featureHtml = ('<div class="rack-info"><a href="/rack/' + firstFeature.fid + '"><img src="' + ((firstFeature.attributes.thumbnail != null) ? firstFeature.attributes.thumbnail.value : '/site_media/img/default-rack.jpg') + '" width="50" /></a><h3><a href="/rack/' + firstFeature.fid + '">' + firstFeature.attributes.name + '</a></h3><h4>' + firstFeature.attributes.address + '</h4>' + ((firstFeature.attributes.verified == null) ? '' : '<h5><em>verified</em></h5>') + '</div>');
          var popup = new OpenLayers.Popup.FramedCloud(
              null,
              feature.geometry.getBounds().getCenterLonLat(),
              null,
              featureHtml,
              {size: new OpenLayers.Size(1, 1),
               offset: new OpenLayers.Pixel(0, 0)},
              true,
              function() { selectControl.unselect(feature); });
          feature.popup = popup;
          map.addPopup(popup);
          if (cluster.length > 1) {
            navHtml = '<div><a class="popupnav prev" href="#">prev</a>&nbsp;<a class="popupnav next" href="#">next</a></div>';
            var clusterIdx = 0;
            var content = popup.contentDiv;
            $(content).append($(navHtml));
            var prev = $(content).find('a.popupnav.prev');
            var next = $(content).find('a.popupnav.next');
            var replaceHtml = function(f) {
              $(content).find('a:first').attr('href', '/rack/' + f.fid);
              var thumb = (f.attributes.thumbnail != null) ? f.attributes.thumbnail.value : '/site_media/img/default-rack.jpg';
              $(content).find('img').attr('src', thumb);
              $(content).find('h3 a').attr('href', '/rack/' + f.fid);
              $(content).find('h3 a').text(f.attributes.name);
              $(content).find('h4').text(f.attributes.address);
              $(content).find('h5').remove();
              if (f.attributes.verified != null) {
                $(content).find('h4').after('<h5><em>verified</em></h5>');
              }
            };
            prev.click(function(e) {
              e.preventDefault();
              clusterIdx = (clusterIdx == 0) ? cluster.length-1 : clusterIdx-1;
              replaceHtml(cluster[clusterIdx]);
              // popup.draw();
            });
            next.click(function(e) {
              e.preventDefault();
              clusterIdx = (clusterIdx == cluster.length-1) ? 0 : clusterIdx+1;
              replaceHtml(cluster[clusterIdx]);
              // popup.draw();
            });
          }
        };
        var featureUnselected = function(feature) {
          map.removePopup(feature.popup);
          feature.popup.destroy();
          feature.popup = null;
        };
        selectControl = new OpenLayers.Control.SelectFeature(racks, {
          onSelect: featureSelected, onUnselect: featureUnselected
        });
        map.addControl(selectControl);
        selectControl.activate();
        return racks;
    };

    var bounds = new OpenLayers.Bounds(-8234063.45026893, 4968638.33081464, -8230209.19302436, 4973585.50729644);
    racks = loadRacks();
    map.addLayers([osm, racks]);
    //map.addLayers([osm]);
    map.zoomToExtent(bounds);

}

function updateFilterBehaviors() {
    var boroSelect = $('#filter-boro');
    var cbSelect = $('#filter-cb');
    boroSelect.change(function(e) {
            e.preventDefault();
            console.log('change');
            var boro = $(this).val();
            $.getJSON('/cbs/' + boro, {}, function(boros) {
                    cbSelect.empty();
                    cbSelect.append('<option value="0">All</option>');
                    var boardNum;
                    for (var i = 0; i < boros.length; i++) {
                        boardNum = boros[i];
                        cbSelect.append('<option value="' + boardNum + '">' + boardNum + '</option>');
                    }
                });
        });
    $('#filter-form').submit(function(e) {
            e.preventDefault();
            var url = $(this).attr("action");
            var vrfy = $('#filter-form input:radio[name=state]:checked').val()
                $.get(url,
                      {boro: boroSelect.val(),
                       cb: cbSelect.val(),
                       verified: vrfy},
                      function(data) {
                          $('ul#racklist').empty().append(data);
                      });
        });
}
