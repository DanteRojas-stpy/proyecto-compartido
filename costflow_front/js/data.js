/**
 * CostFlow - Datos del Sistema (data.js)
 * Estructuras extensibles para navegación, vistas internas y datos de contacto.
 */

const CostFlowData = {
  // Configuración general de la marca y empresa
  brand: {
    name: "CostFlow",
    tagline: "Ahorra tiempo y toma la mejor decisión con CostFlow",
    mascotMessage: "Tu búho vigilante de cotizaciones",
    logoPath: "assets/logo-costflow.png",
    mascotPath: "assets/mascota-buho.png"
  },

  // Datos de contacto y redes sociales (fáciles de modificar)
  contactInfo: {
    linkedin: "https://www.linkedin.com/company/costflow", // placeholder funcional
    phone: "+51 000 000 000",                             // placeholder
    phoneDisplay: "+51 000 000 000",
    phoneTelLink: "tel:+51000000000",
    whatsappUrl: "https://wa.me/51000000000?text=Hola%20CostFlow,%20deseo%20m%C3%A1s%20informaci%C3%B3n",
    email: "contacto@costflow.com",                        // placeholder
    emailMailto: "mailto:contacto@costflow.com?subject=Consulta%20sobre%20CostFlow",
    copyrightYear: 2026,
    copyrightText: "© 2026 CostFlow. Todos los derechos reservados."
  },

  // Estructura extensible del menú "Compara".
  // Permite añadir en el futuro más títulos principales además de "Edificaciones" (ej. "Infraestructura", "Vial", etc.)
  comparaCategories: [
    {
      id: "edificaciones",
      title: "Edificaciones",
      description: "Módulo especializado en proyectos de edificación residencial, comercial e institucional.",
      subcategories: [
        {
          id: "obras-provisionales-preliminares",
          slug: "obras-provisionales-preliminares",
          title: "Obras provisionales y preliminares",
          description: "Sube y compara cotizaciones de casetas de obra, cerramientos, trazo y replanteo, demoliciones y limpieza de terreno.",
          hash: "#/compara/edificaciones/obras-provisionales-preliminares"
        },
        {
          id: "salud-seguridad",
          slug: "salud-seguridad",
          title: "Salud y seguridad",
          description: "Evalúa propuestas para equipos de protección individual (EPIs), señalética de obra, líneas de vida y planes de mitigación de riesgos.",
          hash: "#/compara/edificaciones/salud-seguridad"
        },
        {
          id: "estructuras",
          slug: "estructuras",
          title: "Estructuras",
          description: "Analiza y contrasta presupuestos de excavaciones masivas, concreto f'c=210/280, acero corrugado fy=4200 y encofrados.",
          hash: "#/compara/edificaciones/estructuras"
        },
        {
          id: "arquitectura",
          slug: "arquitectura",
          title: "Arquitectura",
          description: "Compara partidas de muros de albañilería, tabiquería dry-wall, revoques, pisos, enchapes finos, pintura y carpintería.",
          hash: "#/compara/edificaciones/arquitectura"
        },
        {
          id: "instalaciones-sanitarias",
          slug: "instalaciones-sanitarias",
          title: "Instalaciones sanitarias",
          description: "Audita cotizaciones de redes de distribución de agua fría/caliente, desagüe, ventilación, cisterna y cuartos de bombas.",
          hash: "#/compara/edificaciones/instalaciones-sanitarias"
        },
        {
          id: "instalaciones-electricas-mecanicas",
          slug: "instalaciones-electricas-mecanicas",
          title: "Instalaciones eléctricas y mecánicas",
          description: "Compara costos de alimentadores, tableros generales, ductería, bandejas portacables, climatización (HVAC) y grupos electrógenos.",
          hash: "#/compara/edificaciones/instalaciones-electricas-mecanicas"
        },
        {
          id: "otros",
          slug: "otros",
          title: "Otros",
          description: "Espacio para partidas adicionales, ensayos de laboratorio de suelos/concreto, fletes especiales y subcontratos específicos.",
          hash: "#/compara/edificaciones/otros"
        }
      ]
    }
  ],

  // Configuración de la vista "Vigila"
  vigilaView: {
    id: "vigila",
    title: "Vigila",
    uploadAreaTitle: "Cuadro de procura",
    description: "Carga tu cuadro de procura consolidado para monitorear fechas límite, alertar sobrecostos y priorizar automáticamente las mejores cotizaciones recibidas.",
    hash: "#/vigila"
  },

  // Extensiones de archivo permitidas y límites
  uploadSettings: {
    maxSizeBytes: 20 * 1024 * 1024, // 20 Megabytes
    maxSizeDisplay: "20 MB",
    allowedExtensions: [
      ".pdf",
      ".xls", ".xlsx", ".csv",
      ".doc", ".docx",
      ".png", ".jpg", ".jpeg", ".webp"
    ],
    allowedMimeTypes: [
      "application/pdf",
      "application/vnd.ms-excel",
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      "text/csv",
      "application/msword",
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "image/png",
      "image/jpeg",
      "image/webp"
    ]
  }
};

// Exportación compatible si se corre en entorno modular
if (typeof module !== "undefined" && module.exports) {
  module.exports = CostFlowData;
}
