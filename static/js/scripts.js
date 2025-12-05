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
 */
function generateTable(data, targetId, maxRows = null) {
    const container = $(targetId);
    container.empty(); 
    
    if (!data || data.length === 0) {
        container.html('<p>(No se encontraron datos para esta sección)</p>');
        return;
    }

    let message = '';
    let displayData = data;
    
    if (maxRows && data.length > maxRows) {
        displayData = data.slice(0, maxRows);
        message = `<p class="table-note">Mostrando las primeras ${maxRows} de ${data.length} filas.</p>`;
    }

    let html = '<table class="table"><thead><tr>';
    const headers = Object.keys(displayData[0]);
    headers.forEach(key => html += `<th>${escapeHTML(key)}</th>`);
    html += '</tr></thead><tbody>';

    displayData.forEach(row => {
        html += '<tr>';
        headers.forEach(key => {
            const value = row[key] === null ? '<i>null</i>' : escapeHTML(row[key]);
            html += `<td>${value}</td>`;
        });
        html += '</tr>';
    });

    html += '</tbody></table>';
    container.html(message + html);
}


/**
 * Genera una galería de imágenes.
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
    // Se usa innerHTML para permitir el formato Markdown simple de la IA (como h3, strong)
    container.html(`<div class="markdown ${className}">${message}</div>`);
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

// Helper para actualizar las opciones de un dropdown
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

// --- FUNCIÓN CLAVE: ACTUALIZA LA VISIBILIDAD DEL BOTÓN DE DESCARGA ---
function updateDownloadButtonVisibility() {
    const isStorySectionActive = $('#story-section').hasClass('active-page');
    // Chequea si existen imágenes en la galería de gráficos de IA
    const chartsExist = $('#aiChartsGallery').find('.gallery-item').length > 0;
    
    if (isStorySectionActive && chartsExist) {
        $('#downloadZipBtn').show();
    } else {
        $('#downloadZipBtn').hide();
    }
}
// ---------------------------------------------------------------------


// --- FUNCIÓN SECUENCIAL PARA GENERAR GRÁFICOS DE SOPORTE DE LA IA ---
function generateAiCharts() {
    
    const fileInput = $('#file')[0];
    if (fileInput.files.length === 0) {
        showLog('Error: Archivo CSV no cargado.', '#aiChartsLog', true);
        return;
    }
    
    const formData = new FormData();
    formData.append('file', fileInput.files[0]);
    
    $('#aiChartsLog').html('<p>Generando gráficos de soporte (Barra y Líneas)...</p>');
    $('#aiChartsGallery').empty();
    $('#downloadZipBtn').hide(); // Ocultar mientras carga

    $.ajax({
        url: '/generate_ai_charts', 
        type: 'POST',
        data: formData,
        processData: false,
        contentType: false,
        success: function(data) {
            if (data.error) {
                showLog(data.error, '#aiChartsLog', true);
                updateDownloadButtonVisibility();
                return;
            }
            generateGallery(data, '#aiChartsGallery');
            showLog(data.log, '#aiChartsLog');
            
            // *** Muestra el botón de descarga solo si se generaron gráficos ***
            updateDownloadButtonVisibility();
        },
        error: function(jqXHR) {
            showLog('Error generando gráficos de soporte: ' + (jqXHR.responseJSON ? jqXHR.responseJSON.error : jqXHR.responseText), '#aiChartsLog', true);
            updateDownloadButtonVisibility();
        }
    });
}
// ----------------------------------------------------------------------


// --- NUEVA FUNCIÓN: VALIDAR TIPO DE ARCHIVO ---
function validateFile(fileInput) {
    if (fileInput.files.length === 0) {
        return true; // No hay archivo, no hay error.
    }
    const fileName = fileInput.files[0].name;
    // Verifica si la extensión es .csv (insensible a mayúsculas/minúsculas)
    if (!fileName.toLowerCase().endsWith('.csv')) {
        alert('Error: Por favor, sube solo archivos CSV (.csv).');
        // Resetea el input para que el usuario suba el archivo correcto.
        fileInput.value = ''; 
        // Lanza el evento change para limpiar resultados anteriores si los hubiera.
        $(fileInput).trigger('change'); 
        return false;
    }
    return true;
}
// ----------------------------------------------


// ------ LÓGICA DE EVENTOS (jQuery) ------

$(document).ready(function() {

    // Inicialmente, el botón de descarga debe estar oculto
    $('#downloadZipBtn').hide();

    // --- Validación de archivo al seleccionar ---
    $('#file').on('change', function() {
        validateFile(this);
    });

    // --- Lógica de Navegación del Sidebar ---
    $('.nav-sidebar').on('click', '.menu-item', function(e) {
        if ($(this).hasClass('logout')) {
            return; 
        }
        e.preventDefault();

        const targetId = $(this).attr('href');
        
        // 1. Manejo de visibilidad del botón de descarga al cambiar de pestaña
        setTimeout(updateDownloadButtonVisibility, 50); 

        // 2. Actualiza el ítem activo del menú
        $('.nav-sidebar .menu-item').removeClass('active');
        $(this).addClass('active');

        // 3. Muestra/Oculta las secciones
        $('.main-content .container').removeClass('active-page').hide();
        $(targetId).addClass('active-page').fadeIn(400);

        $('.main-content').scrollTop(0);
    });

    // --- Inicialización: Muestra la sección por defecto ---
    $('.main-content .container').hide(); 
    const defaultPage = $('.nav-sidebar .menu-item.active').attr('href');
    if (defaultPage) {
        $(defaultPage).addClass('active-page').show();
    }


    // --- 0) Reseteo al cargar archivo nuevo (Lado del cliente) ---
    $('#file').change(function() {
        // Ejecuta la validación primero
        if (!validateFile(this)) return;

        // Valores por defecto
        $('#group_col').val('estructuraalumno');
        $('#metric_choice').val('__tasa__');
        $('#seq_line_x').val('semestre');
        $('#seq_line_y').val('__tasa__');
        $('#seq_hm_row').val('estructuraalumno');
        $('#seq_hm_col').val('semestre');
        
        // Limpia resultados
        $('#headTable').empty();
        $('#schemaTable').empty();
        $('#anomTable').empty();
        $('#isoTable').empty();
        $('#seqGallery').empty();
        $('#seqLog').empty();
        $('#storyMd').empty();
        $('#aiChartsLog').empty(); 
        $('#aiChartsGallery').html('<p>(Los gráficos se mostrarán aquí después de generar los Insights).</p>'); 
        $('#downloadZipBtn').hide(); // OCULTAR
        
        appState.seq_paths = [];
        appState.seq_captions = [];
        console.log('Estado reseteado por carga de nuevo archivo.');
    });


    // --- 1) Analizar CSV ---
    $('#analyzeBtn').click(function() {
        const fileInput = $('#file')[0];
        if (fileInput.files.length === 0 || !validateFile(fileInput)) {
            if (fileInput.files.length === 0) alert('Por favor, sube un archivo CSV primero.');
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
                generateTable(data.anom, '#anomTable', 100); 
                generateTable(data.iso, '#isoTable', 100); 
                
                updateDropdown('#group_col', data.groups, $('#group_col').val());
                updateDropdown('#metric_choice', data.metrics, data.current_metric);

                // Lógica de autoselección para la secuencia
                const best_group = data.groups.length > 0 ? data.groups[0] : 'col_grupo_1';
                const best_group_2 = data.groups.length > 1 ? data.groups[1] : best_group;
                const best_metric = data.current_metric;

                $('#seq_line_x').val(best_group_2); 
                $('#seq_line_y').val(best_metric); 
                $('#seq_hm_row').val(best_group); 
                $('#seq_hm_col').val(best_group_2);
                
                // Mueve la vista a la sección de resultados
                $('html, body').animate({
                    scrollTop: $("#headTable").offset().top - 200
                }, 500);


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
        if (fileInput.files.length === 0 || !validateFile(fileInput)) {
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

    // --- 3) Generar Historia (CON IA) y Gráficos de Soporte ---
    $('#generateStoryBtn').click(function() {
        const fileInput = $('#file')[0];
        if (fileInput.files.length === 0 || !validateFile(fileInput)) {
            alert('Por favor, sube un archivo CSV primero.');
            return;
        }

        const formData = new FormData();
        // Claves del análisis inicial
        formData.append('file', fileInput.files[0]);
        formData.append('group_col', $('#group_col').val());
        formData.append('metric_choice', $('#metric_choice').val());
        formData.append('method', $('#method').val());
        formData.append('k_iqr', $('#k_iqr').val());
        formData.append('z_thr', $('#z_thr').val());
        formData.append('mad_thr', $('#mad_thr').val());
        formData.append('min_n', $('#min_n').val());
        // Claves de la secuencia para consistencia
        formData.append('seq_topn', $('#seq_topn').val()); 
        formData.append('seq_theme', $('#seq_theme').val());
        formData.append('seq_simple', $('#seq_simple').is(':checked') ? 'on' : 'off');
        formData.append('seq_line_x', $('#seq_line_x').val()); // NEW
        formData.append('seq_line_y', $('#seq_line_y').val()); // NEW

        $('#downloadZipBtn').hide(); // Ocultar al inicio del proceso

        $(this).text('Consultando al Agente IA...').prop('disabled', true);
        $('#storyMd').html('<p>Generando insights y recomendaciones...</p>');
        $('#aiChartsLog').empty();
        $('#aiChartsGallery').html('<p>Esperando la respuesta de la IA...</p>');


        $.ajax({
            url: '/generate_story',
            type: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            success: function(data) {
                if (data.error) {
                    showLog(data.error, '#storyMd', true);
                    $('#aiChartsGallery').empty();
                    return;
                }
                
                // Conversión de Markdown simple a HTML para el frontend
                const storyHtml = data.story
                                    .replace(/### (.*)/g, '<h3>$1</h3>')
                                    .replace(/###\s(.*)/g, '<h3>$1</h3>')
                                    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                                    .replace(/\n/g, '<br>')
                                    .replace(/<br>\* (.*)/g, '<br>&nbsp;&nbsp;&nbsp;• $1')
                                    .replace(/\* (.*)/g, '&nbsp;&nbsp;&nbsp;• $1'); 
                                    
                $('#storyMd').html(storyHtml);
                
                // *** ¡PASO SECUENCIAL CLAVE! ***
                // Después de obtener la historia, genera los gráficos de soporte
                generateAiCharts();
            },
            error: function(jqXHR) {
                showLog(`Error: ${escapeHTML(jqXHR.responseJSON ? jqXHR.responseJSON.error : jqXHR.responseText)}`, '#storyMd', true);
                $('#aiChartsGallery').empty();
            },
            complete: function() {
                $('#generateStoryBtn').text('🧠 Generar Insights y Gráficos').prop('disabled', false);
            }
        });
    });

    // --- 4) Generar Plantillas Individuales (REMOVIDO) ---
    $('#generateTplBtn').click(function() {
        alert("Esta función ha sido deshabilitada. Usa 'Generar Insights y Gráficos' para obtener visualizaciones recomendadas.");
    });
    
    // --- 5) Descargar ZIP (ahora es un enlace directo en la sección IA) ---
    $('#downloadZipBtn').click(function(e) {
         return true;
    });

    // --- 6) LÓGICA DEL LIGHTBOX (Modal) ---
    
    // Abrir el lightbox
    $('.main-content').on('click', '.gallery-image-clickable', function() {
        const src = $(this).attr('src');
        const caption = $(this).data('caption');
        
        $('#lightboxImage').attr('src', src);
        $('#lightboxCaption').text(caption);
        $('#lightboxOverlay').css('display', 'flex').hide().fadeIn(200); 
    });
    
    // Cerrar el lightbox al hacer clic en la 'X' o en el fondo
    $('#lightboxClose, #lightboxOverlay').click(function(e) {
        if ($(e.target).is('#lightboxOverlay') || $(e.target).is('#lightboxClose')) {
            $('#lightboxOverlay').fadeOut(200);
        }
    });
    
    // Evitar que se cierre al hacer clic EN la imagen
    $('#lightboxContent').click(function(e) {
        e.stopPropagation();
    });

});