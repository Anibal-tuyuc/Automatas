/* ==================================================================
   app.js - Revisor de Cadenas
   Proyecto 1, Autómatas y Lenguajes Formales
   Controla la carga de archivos y la animación paso a paso del AFD.
   ================================================================== */

(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);

  // ---------------- Estado de la aplicación ----------------

  const estado = {
    entrada: null,        // {nombre, texto}
    expresiones: null,    // {nombre, texto}
    datos: null,          // respuesta del servidor
    guion: [],            // lista plana de eventos de animación
    indice: 0,
    corriendo: false,
    temporizador: null,
    velocidad: 2000,      // milisegundos por paso
  };

  // ---------------- Carga de archivos ----------------

  function configurarZona(idZona, idInput, idInfo, destino) {
    const zona = $(idZona);
    const input = $(idInput);
    const info = $(idInfo);

    zona.querySelector("[data-abrir]").addEventListener("click", () => input.click());

    input.addEventListener("change", (ev) => {
      if (ev.target.files.length) leerArchivo(ev.target.files[0]);
    });

    ["dragenter", "dragover"].forEach((evento) =>
      zona.addEventListener(evento, (ev) => {
        ev.preventDefault();
        zona.classList.add("encima");
      })
    );

    ["dragleave", "drop"].forEach((evento) =>
      zona.addEventListener(evento, (ev) => {
        ev.preventDefault();
        zona.classList.remove("encima");
      })
    );

    zona.addEventListener("drop", (ev) => {
      const archivo = ev.dataTransfer.files[0];
      if (archivo) leerArchivo(archivo);
    });

    function leerArchivo(archivo) {
      const lector = new FileReader();
      lector.onload = () => {
        estado[destino] = { nombre: archivo.name, texto: lector.result };
        const lineas = lector.result.split(/\r?\n/).filter((l) => l.trim()).length;
        info.innerHTML =
          `&#10003; ${escapar(archivo.name)}<br><span>${lineas} línea(s) con contenido</span>`;
        zona.classList.add("cargado");
        revisarListo();
      };
      lector.onerror = () => mostrarError("No se pudo leer el archivo " + archivo.name);
      lector.readAsText(archivo, "UTF-8");
    }
  }

  function revisarListo() {
    const listo = Boolean(estado.entrada && estado.expresiones);
    $("btnProcesar").disabled = !listo;
    if (listo) fijarIndicador("listo", "Archivos cargados");
  }

  function fijarIndicador(clase, texto) {
    const indicador = $("indicadorEstado");
    indicador.className = "indicador " + clase;
    $("textoEstado").textContent = texto;
  }

  // ---------------- Comunicación con el servidor ----------------

  async function cargarEjemplos() {
    try {
      const respuesta = await fetch("/api/ejemplos");
      const datos = await respuesta.json();

      estado.entrada = { nombre: "Entrada.txt", texto: datos.entrada };
      estado.expresiones = { nombre: "Expresion.txt", texto: datos.expresiones };

      pintarInfoEjemplo("infoEntrada", "zonaEntrada", "Entrada.txt", datos.entrada);
      pintarInfoEjemplo("infoExpresion", "zonaExpresion", "Expresion.txt", datos.expresiones);
      ocultarError();
      revisarListo();
    } catch (err) {
      mostrarError("No se pudieron cargar los ejemplos: " + err.message);
    }
  }

  function pintarInfoEjemplo(idInfo, idZona, nombre, texto) {
    const lineas = texto.split(/\r?\n/).filter((l) => l.trim()).length;
    $(idInfo).innerHTML =
      `&#10003; ${nombre} <span>(ejemplo)</span><br><span>${lineas} línea(s) con contenido</span>`;
    $(idZona).classList.add("cargado");
  }

  async function procesar() {
    ocultarError();
    detener();
    $("btnProcesar").disabled = true;
    $("btnProcesar").textContent = "Construyendo autómatas...";
    fijarIndicador("", "Construyendo autómatas");

    try {
      const respuesta = await fetch("/api/procesar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          entrada: estado.entrada.texto,
          expresiones: estado.expresiones.texto,
          nombre_entrada: estado.entrada.nombre,
          nombre_expresiones: estado.expresiones.nombre,
          guardar: true,
        }),
      });

      const datos = await respuesta.json();
      if (!datos.ok) throw new Error(datos.error || "Error desconocido");

      estado.datos = datos;
      pintarAutomatas(datos.automatas);
      construirGuion(datos.trazas);
      prepararSimulacion();

      if (datos.avisos && datos.avisos.length) {
        mostrarAviso(datos.avisos.join("\n"));
      }

      $("seccionAutomatas").classList.remove("oculto");
      $("seccionSimulacion").classList.remove("oculto");
      $("seccionResultado").classList.add("oculto");
      $("seccionSimulacion").scrollIntoView({ behavior: "smooth", block: "start" });
      fijarIndicador("listo", "Listo para simular");
    } catch (err) {
      mostrarError(err.message);
      fijarIndicador("fallo", "Error");
    } finally {
      $("btnProcesar").disabled = false;
      $("btnProcesar").textContent = "Analizar y construir autómatas";
    }
  }

  // ---------------- Autómatas construidos ----------------

  function pintarAutomatas(automatas) {
    const lista = $("listaAutomatas");
    lista.innerHTML = "";

    automatas.forEach((automata) => {
      const ficha = document.createElement("div");
      ficha.className = "fichaAutomata";

      const filas = automata.tabla
        .map((fila) => {
          const marcas = [];
          if (fila.inicial) marcas.push('<span class="marcaInicial">&rarr;</span>');
          if (fila.aceptacion) marcas.push('<span class="marcaFinal">&#9733;</span>');
          const transiciones = fila.transiciones.length
            ? fila.transiciones
                .map((t) => `${escapar(t.simbolos)} &rarr; ${t.destino}`)
                .join("<br>")
            : '<span style="opacity:.4">(sin salidas)</span>';
          return `<tr>
              <td>${marcas.join(" ")} ${fila.estado}</td>
              <td>${transiciones}</td>
            </tr>`;
        })
        .join("");

      ficha.innerHTML = `
        <div class="encabezadoAutomata">
          <span class="nombreAutomata">${escapar(automata.nombre)}</span>
          <code class="patronAutomata">${escapar(automata.patron)}</code>
          <div class="insignias">
            <span class="insignia">AFN: ${automata.estados_afn}</span>
            <span class="insignia">AFD: ${automata.estados_afd}</span>
          </div>
        </div>
        <div class="cuerpoAutomata">
          <table class="tablaTransiciones">
            <thead><tr><th>Estado</th><th>Transiciones</th></tr></thead>
            <tbody>${filas}</tbody>
          </table>
        </div>`;

      ficha
        .querySelector(".encabezadoAutomata")
        .addEventListener("click", () => ficha.classList.toggle("abierta"));

      lista.appendChild(ficha);
    });
  }

  // ---------------- Construcción del guion de animación ----------------
  /*
     Cada entrada del guion es un evento que la animación reproduce
     cada "velocidad" milisegundos:
       {tipo:"inicio_cadena"}  -> pinta la cinta
       {tipo:"inicio_intento"} -> cambia la expresión que se evalúa
       {tipo:"paso"}           -> consume un carácter (q_i -> q_j)
       {tipo:"fin_intento"}    -> acepta o rechaza esa expresión
       {tipo:"fin_cadena"}     -> clasificación final de la cadena
  */

  function construirGuion(trazas) {
    const guion = [];

    trazas.forEach((traza, numero) => {
      guion.push({
        tipo: "inicio_cadena",
        cadena: traza.cadena,
        numero: numero + 1,
        total: trazas.length,
      });

      traza.intentos.forEach((intento) => {
        guion.push({
          tipo: "inicio_intento",
          cadena: traza.cadena,
          expresion: intento.expresion,
          patron: intento.patron,
        });

        intento.pasos.forEach((paso) => {
          guion.push({
            tipo: "paso",
            cadena: traza.cadena,
            expresion: intento.expresion,
            paso: paso,
          });
        });

        guion.push({
          tipo: "fin_intento",
          cadena: traza.cadena,
          expresion: intento.expresion,
          aceptada: intento.aceptada,
          estadoFinal: intento.estado_final,
          motivo: intento.motivo,
        });
      });

      guion.push({
        tipo: "fin_cadena",
        cadena: traza.cadena,
        categoria: traza.categoria,
      });
    });

    estado.guion = guion;
    estado.indice = 0;
  }

  // ---------------- Reproducción ----------------

  function prepararSimulacion() {
    detener();
    estado.indice = 0;
    $("listaBitacora").innerHTML = "";
    $("cinta").innerHTML = "";
    $("cadenaActual").textContent = "—";
    $("expresionActual").textContent = "—";
    $("estadoAnterior").textContent = "q0";
    $("estadoActual").textContent = "q0";
    $("estadoActual").className = "burbujaEstado activa";
    $("estadoAnterior").className = "burbujaEstado";
    $("simboloTransicion").textContent = "—";
    $("claseTransicion").textContent = "";
    $("veredicto").className = "veredicto";
    $("rellenoProgreso").style.width = "0%";
    $("textoProgreso").textContent =
      `Listo para iniciar  ·  ${estado.guion.length} pasos en total`;
    actualizarBotones();
  }

  function actualizarBotones() {
    const hayGuion = estado.guion.length > 0;
    const terminado = estado.indice >= estado.guion.length;
    $("btnIniciar").disabled = !hayGuion || terminado || estado.corriendo;
    $("btnPausar").disabled = !estado.corriendo;
    $("btnPaso").disabled = !hayGuion || terminado || estado.corriendo;
    $("btnFinal").disabled = !hayGuion || terminado;
    $("btnIniciar").innerHTML =
      estado.indice > 0 && !terminado ? "&#9654; Continuar" : "&#9654; Iniciar";
  }

  function iniciar() {
    if (estado.indice >= estado.guion.length) return;
    estado.corriendo = true;
    fijarIndicador("corriendo", "Simulando");
    actualizarBotones();
    reproducir();
  }

  function reproducir() {
    if (!estado.corriendo) return;

    if (estado.indice >= estado.guion.length) {
      terminar();
      return;
    }

    ejecutarEvento(estado.guion[estado.indice]);
    estado.indice += 1;
    actualizarProgreso();

    estado.temporizador = setTimeout(reproducir, estado.velocidad);
  }

  function pausar() {
    estado.corriendo = false;
    clearTimeout(estado.temporizador);
    fijarIndicador("listo", "En pausa");
    actualizarBotones();
  }

  function detener() {
    estado.corriendo = false;
    clearTimeout(estado.temporizador);
  }

  function unPaso() {
    if (estado.indice >= estado.guion.length) return;
    ejecutarEvento(estado.guion[estado.indice]);
    estado.indice += 1;
    actualizarProgreso();
    if (estado.indice >= estado.guion.length) terminar();
    actualizarBotones();
  }

  function saltarAlFinal() {
    detener();
    while (estado.indice < estado.guion.length) {
      ejecutarEvento(estado.guion[estado.indice], true);
      estado.indice += 1;
    }
    actualizarProgreso();
    terminar();
  }

  function reiniciar() {
    prepararSimulacion();
    $("seccionResultado").classList.add("oculto");
    fijarIndicador("listo", "Listo para simular");
  }

  function terminar() {
    detener();
    mostrarResultados();
    fijarIndicador("terminado", "Proceso finalizado");
    actualizarBotones();
    $("textoProgreso").textContent =
      `Proceso finalizado  ·  ${estado.guion.length} pasos ejecutados`;
  }

  function actualizarProgreso() {
    const porcentaje = estado.guion.length
      ? (estado.indice / estado.guion.length) * 100
      : 0;
    $("rellenoProgreso").style.width = porcentaje.toFixed(1) + "%";
    if (estado.indice < estado.guion.length) {
      $("textoProgreso").textContent =
        `Paso ${estado.indice} de ${estado.guion.length}  ·  ` +
        `${porcentaje.toFixed(0)}%`;
    }
  }

  // ---------------- Ejecución de cada evento ----------------

  function ejecutarEvento(evento, silencioso) {
    switch (evento.tipo) {
      case "inicio_cadena":
        pintarCinta(evento.cadena);
        $("cadenaActual").textContent = evento.cadena;
        $("expresionActual").textContent = "—";
        $("veredicto").className = "veredicto";
        reiniciarBurbujas();
        if (!silencioso) {
          registrar(
            "info",
            `[${evento.numero}/${evento.total}]`,
            evento.cadena,
            "analizando"
          );
        }
        break;

      case "inicio_intento":
        pintarCinta(evento.cadena);
        $("expresionActual").textContent = evento.expresion;
        $("veredicto").className = "veredicto";
        reiniciarBurbujas();
        break;

      case "paso":
        animarPaso(evento.cadena, evento.paso);
        break;

      case "fin_intento": {
        const caja = $("veredicto");
        caja.className =
          "veredicto visible " + (evento.aceptada ? "acepta" : "rechaza");
        caja.textContent = evento.aceptada
          ? `ACEPTA  ·  ${evento.expresion}  ·  estado final ${evento.estadoFinal}`
          : `RECHAZA  ·  ${evento.expresion}  ·  ${evento.motivo || "no coincide"}`;
        $("estadoActual").className =
          "burbujaEstado " + (evento.aceptada ? "aceptacion" : "rechazo");
        break;
      }

      case "fin_cadena": {
        const esError = evento.categoria === "ERROR";
        if (!silencioso) {
          registrar(
            esError ? "malo" : "ok",
            esError ? "✗" : "✓",
            evento.cadena,
            evento.categoria
          );
        } else {
          registrar(
            esError ? "malo" : "ok",
            esError ? "✗" : "✓",
            evento.cadena,
            evento.categoria
          );
        }
        break;
      }
    }
  }

  function reiniciarBurbujas() {
    $("estadoAnterior").textContent = "q0";
    $("estadoAnterior").className = "burbujaEstado";
    $("estadoActual").textContent = "q0";
    $("estadoActual").className = "burbujaEstado activa";
    $("simboloTransicion").textContent = "—";
    $("claseTransicion").textContent = "";
  }

  function pintarCinta(cadena) {
    const cinta = $("cinta");
    cinta.innerHTML = "";
    for (const ch of cadena) {
      const celda = document.createElement("div");
      const vista = nombreCaracter(ch);
      celda.className = "celda" + (vista !== ch ? " especial" : "");
      celda.textContent = vista;
      cinta.appendChild(celda);
    }
  }

  function animarPaso(cadena, paso) {
    const celdas = $("cinta").children;

    for (let i = 0; i < celdas.length; i++) {
      celdas[i].className = celdas[i].className.replace(
        /\s*(consumida|actual|rechazada)/g,
        ""
      );
      if (i < paso.indice) celdas[i].classList.add("consumida");
    }

    const celda = celdas[paso.indice];
    if (celda) {
      celda.classList.add(paso.valido ? "actual" : "rechazada");
      celda.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
    }

    $("estadoAnterior").textContent = paso.desde;
    $("estadoAnterior").className = "burbujaEstado";
    $("estadoActual").textContent = paso.hacia;
    $("estadoActual").className =
      "burbujaEstado " + (paso.valido ? "activa" : "rechazo");
    $("simboloTransicion").textContent = "'" + paso.caracter_vista + "'";
    $("claseTransicion").textContent = paso.valido ? paso.clase : "sin transición";
  }

  function registrar(clase, marca, cadena, categoria) {
    const lista = $("listaBitacora");
    const fila = document.createElement("div");
    fila.className = "registro " + clase;
    fila.innerHTML =
      `<span class="flecha">${marca}</span>` +
      `<span class="cad">${escapar(cadena)}</span>` +
      `<span class="cat">${escapar(categoria)}</span>`;
    lista.appendChild(fila);
    lista.scrollTop = lista.scrollHeight;
  }

  // ---------------- Resultados ----------------

  function mostrarResultados() {
    if (!estado.datos) return;
    const resumen = estado.datos.resumen;

    $("rejillaMetricas").innerHTML = `
      ${metrica("azul", resumen.total_leidas, "Líneas leídas")}
      ${metrica("verde", resumen.clasificadas, "Clasificadas")}
      ${metrica("rojo", resumen.errores, "ERROR")}
      ${metrica("gris", resumen.vacias, "Líneas vacías")}
      ${metrica("azul", estado.datos.expresiones.length, "Expresiones")}`;

    const categorias = Object.entries(resumen.por_categoria).sort(
      (a, b) => b[1] - a[1]
    );
    $("rejillaCategorias").innerHTML = categorias
      .map(
        ([nombre, cantidad]) => `
        <div class="filaCategoria ${nombre === "ERROR" ? "esError" : ""}">
          <span class="nom">${escapar(nombre)}</span>
          <span class="num">${cantidad}</span>
        </div>`
      )
      .join("");

    $("archivoSalida").textContent = estado.datos.salida_texto || "(vacío)";
    $("rutaSalida").textContent = estado.datos.archivos.salida
      ? "Guardado en: " + estado.datos.archivos.salida
      : "No se pudo guardar en disco; use el botón de descarga.";

    $("seccionResultado").classList.remove("oculto");
    $("seccionResultado").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function metrica(color, valor, nombre) {
    return `<div class="metrica ${color}">
        <div class="valor">${valor}</div>
        <div class="nombre">${nombre}</div>
      </div>`;
  }

  function descargar() {
    if (!estado.datos) return;
    const blob = new Blob([estado.datos.salida_texto], {
      type: "text/plain;charset=utf-8",
    });
    const enlace = document.createElement("a");
    enlace.href = URL.createObjectURL(blob);
    enlace.download = "Salida.txt";
    enlace.click();
    URL.revokeObjectURL(enlace.href);
  }

  async function copiar() {
    if (!estado.datos) return;
    try {
      await navigator.clipboard.writeText(estado.datos.salida_texto);
      const boton = $("btnCopiar");
      const original = boton.textContent;
      boton.textContent = "✓ Copiado";
      setTimeout(() => (boton.textContent = original), 1600);
    } catch (err) {
      mostrarError("No se pudo copiar: " + err.message);
    }
  }

  // ---------------- Utilidades ----------------

  function nombreCaracter(ch) {
    const especiales = { " ": "ESP", "\t": "TAB", "\n": "NL", "\r": "CR" };
    if (especiales[ch]) return especiales[ch];
    if (ch.charCodeAt(0) < 32) return "\\x" + ch.charCodeAt(0).toString(16);
    return ch;
  }

  function escapar(texto) {
    const div = document.createElement("div");
    div.textContent = texto == null ? "" : String(texto);
    return div.innerHTML;
  }

  function mostrarError(mensaje) {
    const caja = $("cajaError");
    caja.className = "aviso";
    caja.textContent = mensaje;
    caja.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function mostrarAviso(mensaje) {
    const caja = $("cajaError");
    caja.className = "aviso alerta";
    caja.textContent = "Avisos:\n" + mensaje;
  }

  function ocultarError() {
    $("cajaError").className = "aviso oculto";
  }

  // ---------------- Conexión de eventos ----------------

  configurarZona("zonaEntrada", "archivoEntrada", "infoEntrada", "entrada");
  configurarZona("zonaExpresion", "archivoExpresion", "infoExpresion", "expresiones");

  $("btnEjemplos").addEventListener("click", cargarEjemplos);
  $("btnProcesar").addEventListener("click", procesar);
  $("btnIniciar").addEventListener("click", iniciar);
  $("btnPausar").addEventListener("click", pausar);
  $("btnPaso").addEventListener("click", unPaso);
  $("btnFinal").addEventListener("click", saltarAlFinal);
  $("btnReiniciar").addEventListener("click", reiniciar);
  $("btnDescargar").addEventListener("click", descargar);
  $("btnCopiar").addEventListener("click", copiar);

  $("velocidad").addEventListener("input", (ev) => {
    const segundos = parseFloat(ev.target.value);
    estado.velocidad = segundos * 1000;
    $("valorVelocidad").textContent = segundos.toFixed(1);
  });

  // Atajos de teclado
  document.addEventListener("keydown", (ev) => {
    if (ev.target.tagName === "INPUT" || ev.target.tagName === "TEXTAREA") return;
    if (ev.code === "Space") {
      ev.preventDefault();
      estado.corriendo ? pausar() : iniciar();
    } else if (ev.code === "ArrowRight") {
      ev.preventDefault();
      unPaso();
    } else if (ev.code === "KeyR") {
      reiniciar();
    }
  });
})();
