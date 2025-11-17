function toggleAccordion(id) {
    const content = document.getElementById(id);
    content.style.display = content.style.display === 'block' ? 'none' : 'block';
}

// ------ ESTADO GLOBAL ------
const appState = {
    seq_paths: [],
    seq_captions: []
};

// ------ HELPERS DE RENDERIZADO ------

/**
 * Genera una tabla HTML a partir de un array de objetos (de JSON)
 * Con límite de 'maxRows' para no quebrar el navegador.
 */
function generateTable(data, targetId, maxRows = null) {
    const container = $(targetId);
    container.empty(); // Limpiar contenido anterior
    
    if (!data || data.length === 0) {
        container.html('<p>(No se encontraron datos para esta sección)</p>');
        return;
    }

    let message = '';
    let displayData = data;
    
    // Lógica para truncar los datos si se pasa el límite
    if (maxRows && data.length > maxRows) {
        displayData = data.slice(0, maxRows);
        // Corregido: class="table-note"
        message = `<p class="table-note">Mostrando las primeras ${maxRows} de ${data.length} filas.</p>`;
    }

    let html = '<table class="table"><thead><tr>';
    // Usar displayData para las cabeceras por si data[0] existe pero displayData no
    const headers = Object.keys(displayData[0]);
    headers.forEach(key => html += `<th>${escapeHTML(key)}</th>`);
    html += '</tr></thead><tbody>';

    // Usar 'displayData' (los datos truncados) en lugar de 'data'
    displayData.forEach(row => {
        html += '<tr>';
        headers.forEach(key => {
            // Maneja 'null' que viene del JSON (fix para el error de NaN)
            const value = row[key] === null ? '<i>null</i>' : escapeHTML(row[key]);
            html += `<td>${value}</td>`;
        });
        html += '</tr>';
    });

    html += '</tbody></table>';
    container.html(message + html);
}


/**
 * ¡MODIFICADO PARA LIGHTBOX!
 * Genera una galería de imágenes.
 * Ya no usa <a>, añade una clase 'gallery-image-clickable'
 */
function generateGallery(data, targetId) {
    const container = $(targetId);
    container.empty();
    
    if (!data.images || data.images.length === 0) {
        container.html('<p>(No se generaron imágenes)</p>');
        return;
    }

    let html = '<div class="gallery">';
    data.images.forEach((src, index) => {
        const caption = data.captions[index] || 'Imagen';
        const uniqueSrc = `${src}?t=${new Date().getTime()}`; 
        html += `
            <div class="gallery-item">
                <img src="${uniqueSrc}" 
                     alt="${escapeHTML(caption)}" 
                     data-caption="${escapeHTML(caption)}" 
                     class="gallery-image-clickable">
                <p>${escapeHTML(caption)}</p>
            </div>
        `;
    });
    html += '</div>';
    container.html(html);
}


function showLog(message, targetId, isError = false) {
    const container = $(targetId);
    const className = isError ? 'log-error' : 'log-success';
    container.html(`<div class="markdown ${className}">${escapeHTML(message)}</div>`);
}

function escapeHTML(str) {
    if (str === null || str === undefined) return '';
    return String(str).replace(/[&<>"']/g, function(m) {
        return {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#39;'
        }[m];
    });
}

// ------ LÓGICA DE EVENTOS (jQuery) ------

$(document).ready(function() {

    // --- 0) Reseteo al cargar archivo nuevo ---
    $('#file').change(function() {
        $('#group_col').val('estructuraalumno');
        $('#metric_choice').val('__tasa__');
        $('#seq_line_x').val('semestre');
        $('#seq_line_y').val('__tasa__');
        $('#seq_hm_row').val('estructuraalumno');
        $('#seq_hm_col').val('semestre');
        $('#tpl_group_col').val('estructuraalumno');
        $('#tpl_metric_col').val('__tasa__');
        $('#tpl_line_x').val('semestre');
        $('#tpl_line_y').val('__tasa__');
        $('#tpl_hm_row').val('estructuraalumno');
        $('#tpl_hm_col').val('semestre');
        $('#headTable').empty();
        $('#schemaTable').empty();
        $('#anomTable').empty();
        $('#isoTable').empty();
        $('#seqGallery').empty();
        $('#seqLog').empty();
        $('#storyMd').empty();
        $('#tplGallery').empty();
        $('#tplLog').empty();
        appState.seq_paths = [];
        appState.seq_captions = [];
        console.log('Estado reseteado por carga de nuevo archivo.');
    });


    // --- 1) Analizar CSV ---
    $('#analyzeBtn').click(function() {
        const fileInput = $('#file')[0];
        if (fileInput.files.length === 0) {
            alert('Por favor, sube un archivo CSV primero.');
            return;
        }

        const formData = new FormData();
        formData.append('file', fileInput.files[0]);
        formData.append('method', $('#method').val());
        formData.append('group_col', $('#group_col').val()); 
        formData.append('metric_choice', $('#metric_choice').val());
        formData.append('k_iqr', $('#k_iqr').val());
        formData.append('z_thr', $('#z_thr').val());
        formData.append('mad_thr', $('#mad_thr').val());
        formData.append('min_n', $('#min_n').val());
        formData.append('iso_frac', $('#iso_frac').val());
        
        $(this).text('Analizando...').prop('disabled', true);

        $.ajax({
            url: '/analyze',
            type: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            success: function(data) {
                if (data.error) {
                    alert('Error: ' + data.error);
                    return;
                }
                
                generateTable(data.head, '#headTable');
                generateTable(data.schema, '#schemaTable');
                generateTable(data.anom, '#anomTable', 100); // Límite de 100 filas
                generateTable(data.iso, '#isoTable', 100); // Límite de 100 filas
                
                updateDropdown('#group_col', data.groups, $('#group_col').val());
                updateDropdown('#metric_choice', data.metrics, $('#metric_choice').val());

                const best_group = data.groups.length > 0 ? data.groups[0] : 'col_grupo_1';
                const best_group_2 = data.groups.length > 1 ? data.groups[1] : best_group;
                
                let best_metric = '__tasa__';
                if (data.metrics.length > 0) {
                    best_metric = data.metrics.find(m => m !== '__tasa__') || data.metrics[0];
                }

                $('#seq_line_x').val(best_group_2); 
                $('#seq_line_y').val(best_metric); 
                $('#seq_hm_row').val(best_group); 
                $('#seq_hm_col').val(best_group_2);
                
                $('#tpl_group_col').val(best_group);
                $('#tpl_metric_col').val(best_metric);
                $('#tpl_line_x').val(best_group_2);
                $('#tpl_line_y').val(best_metric);
                $('#tpl_hm_row').val(best_group);
                $('#tpl_hm_col').val(best_group_2);
                
                $('#metric_choice').val(best_metric);

            },
            error: function(jqXHR) {
                let errorMsg = 'Error al analizar CSV.';
                try {
                    const err = JSON.parse(jqXHR.responseText);
                    if(err.error) {
                        errorMsg = "Error: " + err.error;
                    } else if(err.anom && err.anom[0].mensaje) {
                        errorMsg = "Error en JSON: " + err.anom[0].mensaje;
                    } else {
                        errorMsg = "Error en JSON: " + jqXHR.responseText;
                    }
                } catch(e) {
                    errorMsg = (jqXHR.responseJSON ? jqXHR.responseJSON.error : jqXHR.responseText);
                }
                alert(errorMsg);
            },
            complete: function() {
                $('#analyzeBtn').text('Analizar CSV').prop('disabled', false);
            }
        });
    });

    // --- 2) Generar Secuencia Nativa ---
    $('#generateSeqBtn').click(function() {
        const fileInput = $('#file')[0];
        if (fileInput.files.length === 0) {
            alert('Por favor, sube un archivo CSV primero.');
            return;
        }

        const formData = new FormData();
        formData.append('file', fileInput.files[0]);
        formData.append('group_col', $('#group_col').val());
        formData.append('metric_choice', $('#metric_choice').val());
        formData.append('seq_theme', $('#seq_theme').val());
        formData.append('seq_simple', $('#seq_simple').is(':checked') ? 'on' : 'off');
        formData.append('seq_topn', $('#seq_topn').val());
        formData.append('seq_norm', $('#seq_norm').is(':checked') ? 'on' : 'off');
        formData.append('seq_line_x', $('#seq_line_x').val());
        formData.append('seq_line_y', $('#seq_line_y').val());
        formData.append('seq_hm_row', $('#seq_hm_row').val());
        formData.append('seq_hm_col', $('#seq_hm_col').val());
        formData.append('seq_title', $('#seq_title').val());
        formData.append('seq_subt', $('#seq_subt').val());

        $(this).text('Generando...').prop('disabled', true);
        $('#seqGallery').html('<p>Generando 6 pasos (esto puede tardar)...</p>');
        showLog('', '#seqLog');

        $.ajax({
            url: '/generate_sequence',
            type: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            success: function(data) {
                if (data.error) {
                    showLog(data.error, '#seqLog', true);
                    $('#seqGallery').empty();
                    return;
                }
                generateGallery(data, '#seqGallery');
                showLog(data.log, '#seqLog');
                appState.seq_paths = data.images;
                appState.seq_captions = data.captions;
            },
            error: function(jqXHR) {
                showLog('Error generando secuencia: ' + (jqXHR.responseJSON ? jqXHR.responseJSON.error : jqXHR.responseText), '#seqLog', true);
                $('#seqGallery').empty();
            },
            complete: function() {
                $('#generateSeqBtn').text('Generar Secuencia Nativa').prop('disabled', false);
            }
        });
    });

    // --- 3) Generar Historia (CON IA) ---
    $('#generateStoryBtn').click(function() {
        const fileInput = $('#file')[0];
        if (fileInput.files.length === 0) {
            alert('Por favor, sube un archivo CSV primero.');
            return;
        }
        // Ya no se basa en la secuencia, sino en el análisis
        // if (appState.seq_paths.length === 0) {
        //     alert('Debes generar una secuencia primero para crear una historia basada en ella.');
        //     return;
        // }

        const formData = new FormData();
        formData.append('file', fileInput.files[0]);
        formData.append('group_col', $('#group_col').val());
        formData.append('metric_choice', $('#metric_choice').val());
        formData.append('method', $('#method').val());
        formData.append('k_iqr', $('#k_iqr').val());
        formData.append('z_thr', $('#z_thr').val());
        formData.append('mad_thr', $('#mad_thr').val());
        formData.append('min_n', $('#min_n').val());
        // Pasamos el TopN de la secuencia para que la IA vea los mismos datos
        formData.append('seq_topn', $('#seq_topn').val()); 
        
        // (Ya no necesitamos pasar paths y captions)
        // appState.seq_paths.forEach(path => formData.append('seq_paths[]', path));
        // appState.seq_captions.forEach(cap => formData.append('seq_captions[]', cap));

        $(this).text('Consultando al Agente IA...').prop('disabled', true);
        $('#storyMd').html('<p>Generando insights y recomendaciones...</p>');

        $.ajax({
            url: '/generate_story',
            type: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            success: function(data) {
                if (data.error) {
                    $('#storyMd').html(`<p class="log-error">${escapeHTML(data.error)}</p>`);
                    return;
                }
                // La API de IA devuelve Markdown, así que necesitamos una librería
                // o una conversión simple. Usaremos una simple por ahora.
                const storyHtml = data.story
                                    .replace(/### (.*)/g, '<h3>$1</h3>')
                                    .replace(/###\s(.*)/g, '<h3>$1</h3>')
                                    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                                    .replace(/\* (.*)/g, '<li>$1</li>')
                                    .replace(/\n/g, '<br>');
                $('#storyMd').html(storyHtml);
            },
            error: function(jqXHR) {
                $('#storyMd').html(`<p class="log-error">Error: ${escapeHTML(jqXHR.responseJSON ? jqXHR.responseJSON.error : jqXHR.responseText)}</p>`);
            },
            complete: function() {
                $('#generateStoryBtn').text('🧠 Generar Insights con IA').prop('disabled', false);
            }
        });
    });

    // --- 4) Generar Plantillas Individuales ---
    $('#generateTplBtn').click(function() {
        const fileInput = $('#file')[0];
        if (fileInput.files.length === 0) {
            alert('Por favor, sube un archivo CSV primero.');
            return;
        }

        const formData = new FormData();
        formData.append('file', fileInput.files[0]);
        $('input[name="tpl_chart_types"]:checked').each(function() {
            // Arreglo para que envíe como lista
            formData.append('tpl_chart_types[]', $(this).val()); 
        });
        formData.append('tpl_theme', $('#tpl_theme').val());
        formData.append('tpl_simple', $('#tpl_simple').is(':checked') ? 'on' : 'off');
        formData.append('tpl_group_col', $('#tpl_group_col').val());
        formData.append('tpl_metric_col', $('#tpl_metric_col').val());
        formData.append('tpl_topn', $('#tpl_topn').val());
        formData.append('tpl_norm', $('#tpl_norm').is(':checked') ? 'on' : 'off');
        formData.append('tpl_line_x', $('#tpl_line_x').val());
        formData.append('tpl_line_y', $('#tpl_line_y').val());
        formData.append('tpl_hm_row', $('#tpl_hm_row').val());
        formData.append('tpl_hm_col', $('#tpl_hm_col').val());
        formData.append('tpl_title', $('#tpl_title').val());
        formData.append('tpl_subtitle', $('#tpl_subtitle').val());
        
        $(this).text('Generando...').prop('disabled', true);
        $('#tplGallery').html('<p>Generando plantillas seleccionadas...</p>');
        showLog('', '#tplLog');

        $.ajax({
            url: '/generate_templates',
            type: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            success: function(data) {
                if (data.error) {
                    showLog(data.error, '#tplLog', true);
                    $('#tplGallery').empty();
                    return;
                }
                generateGallery(data, '#tplGallery');
                showLog(data.log, '#tplLog');
            },
            error: function(jqXHR) {
                showLog('Error generando plantillas: ' + (jqXHR.responseJSON ? jqXHR.responseJSON.error : jqXHR.responseText), '#tplLog', true);
                $('#tplGallery').empty();
            },
            complete: function() {
                $('#generateTplBtn').text('Generar plantillas individuales').prop('disabled', false);
            }
        });
    });

    // --- 5) Descargar ZIP ---
    $('#downloadZipBtn').click(function() {
        window.location.href = '/download_zip';
    });

    // --- 6) LÓGICA DEL LIGHTBOX (Modal) ---
    
    // Abrir el lightbox
    $('.container').on('click', '.gallery-image-clickable', function() {
        const src = $(this).attr('src');
        const caption = $(this).data('caption');
        
        $('#lightboxImage').attr('src', src);
        $('#lightboxCaption').text(caption);
        $('#lightboxOverlay').css('display', 'flex').hide().fadeIn(200); 
    });
    
    // Cerrar el lightbox al hacer clic en la 'X' o en el fondo
    $('#lightboxClose, #lightboxOverlay').click(function() {
        $('#lightboxOverlay').fadeOut(200);
    });
    
    // Evitar que se cierre al hacer clic EN la imagen
    $('#lightboxContent').click(function(e) {
        e.stopPropagation();
    });

});

/**
 * Helper para actualizar las opciones de un dropdown
 */
function updateDropdown(selectId, options, currentValue) {
    const $select = $(selectId);
    $select.empty();
    
    if (!options || options.length === 0) {
        $select.append($('<option>', { value: '', text: 'N/A' }));
        return;
    }
    
    if (selectId === '#metric_choice' && !options.includes('__tasa__')) {
         options.unshift('__tasa__');
    }

    options.forEach(option => {
        $select.append($('<option>', {
            value: option,
            text: option
        }));
    });
    
    if (options.includes(currentValue)) {
        $select.val(currentValue);
    } else {
        $select.val(options[0]);
    }
}