function _onload() {
    loadMap();
    updateFilterBehaviors();
}

function loadMap() {
  $('#verify-map').map(fixcityDefaultGqueryMapOptions);
}

function updateFilterBehaviors() {
    var boroSelect = $('#filter-boro');
    var cbSelect = $('#filter-cb');
    boroSelect.change(function(e) {
            e.preventDefault();
            var boro = $(this).val();
            $.getJSON('/cbs/' + boro, {}, function(boros) {
                    cbSelect.empty();
                    cbSelect.append('<option value="0">All</option>');
                    var boardArray, boardNum, boardGid;
                    for (var i = 0; i < boros.length; i++) {
                        boardArray = boros[i];
                        boardNum = boardArray[0];
                        boardGid = boardArray[1];
                        cbSelect.append('<option value="' + boardGid + '">' + boardNum + '</option>');
                    }
                });
        });
    var getParamsFn = function() {
        var vrfy = $('#filter-form input:radio[name=state]:checked').val();
         return {verified: vrfy,
                 boro: boroSelect.val(),
                 cb: cbSelect.val()
                 };
    };
    var fetchNewDataFn = function(page) {
        var url = $('#filter-form').attr('action');
        var params = getParamsFn();
        if (page) {
            params.page = page;
        }
        $.get(url,
              params,
              function(data) {
                  $('#racks').empty().append(data);
                  // and add the pagination behavior to the new prev/next links
                  $('#pagination a').click(addPaginationBehavior);
              });
    };
    var createOutlinedLayer = function(url) {
        var style = new OpenLayers.Style({
                fillOpacity: 0,
                strokeWidth: 1,
                strokeColor: "#f35824"
            });
        var outlineLayer = new OpenLayers.Layer.Vector("Outline", {
                projection: map.displayProjection,
                strategies: [
                             new OpenLayers.Strategy.Fixed()
                             ],
                protocol: new OpenLayers.Protocol.HTTP({
                        url: url,
                        params: {},
                        format: new OpenLayers.Format.KML()
                    }),
                styleMap: new OpenLayers.StyleMap({
                        "default": style
                    })
            });
        outlineLayer.events.on({
                loadend: function(evt) {
                    var layer = evt.object;
                    var bounds = layer.getDataExtent();
                    map.zoomToExtent(bounds);
                }
            });
        return outlineLayer;
    }
    var updateMapFn = function() {
        var params = getParamsFn();
        var racksUrl = '/racks/requested.kml?' + jQuery.param(params);
        var outlineUrl = null;
        var racksLayer = map.layers[1];
        var outlineLayer = map.layers[2];

        racksLayer.refresh({url: racksUrl});

        if (params.cb == "0") {
            outlineUrl = '/borough/' + params.boro + '.kml';
        } else {
            outlineUrl = '/communityboard/' + params.cb + '.kml';
        }
        // we don't always have an outline layer on the map
        if (outlineLayer) {
            outlineLayer.refresh({url: outlineUrl});
        } else {
            outlineLayer = createOutlinedLayer(outlineUrl);
            map.addLayer(outlineLayer);
        }
    };
    $('#filter-form').submit(function(e) {
            e.preventDefault();
            // update rack list on left sidebar
            var page = $('#pagination .sectionlink a:not([href])').text();
            fetchNewDataFn(page);
            updateMapFn();
        });
    var addPaginationBehavior = function(e) {
        var href = $(this).attr('href');
        if (!href)
            return;
        var page = href.substring(1);
        fetchNewDataFn(page);
    };
    // used to use live events, but that was causing a strange
    // interaction with the map and the filter form
    // all clicks were triggering the live event behavior, and a map
    // appeared to be injecting itself into the boro select
    // so we just add the pagination behavior every time we update
    // the filter
    $('#pagination a').click(addPaginationBehavior);
}

if (jQuery.browser.msie) {
    jQuery(window).load(function () {
        _onload();
    });
} else {
    jQuery(document).ready(function () {
        _onload();
    });
}
