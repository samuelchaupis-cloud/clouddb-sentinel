-- =============================================================================
-- setup_demo_data.sql - Datos de Prueba Empresariales para CloudDB Sentinel
-- =============================================================================
-- Propósito: Poblar los schemas b2b_crm y telecomunicaciones con datos
--            ficticios pero realistas para validar el health check y
--            los módulos de monitoreo de bases de datos.
--
-- Empresas simuladas: Sector telecomunicaciones y tecnología B2B Perú/LATAM
-- Servicios: MPLS, SD-WAN, Cloud Hosting, DRaaS, FTTH Empresarial
-- Total de registros: ~2800 rows distribuidos en 10 tablas
--
-- Ejecución: psql -U postgres -d clouddb_sentinel_demo -f setup_demo_data.sql
-- =============================================================================

-- Configuración de sesión
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;

-- =============================================================================
-- SCHEMA: b2b_crm
-- CRM corporativo para gestión de clientes, contratos y facturación B2B
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS b2b_crm;

-- -----------------------------------------------------------------------------
-- Tabla: b2b_crm.clientes
-- Directorio maestro de clientes corporativos
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS b2b_crm.clientes (
    id                  SERIAL PRIMARY KEY,
    ruc                 VARCHAR(11)  NOT NULL UNIQUE,
    razon_social        VARCHAR(200) NOT NULL,
    nombre_comercial    VARCHAR(150),
    sector              VARCHAR(80)  NOT NULL,
    segmento            VARCHAR(30)  NOT NULL,  -- ENTERPRISE | PYME | GOBIERNO
    contacto_nombre     VARCHAR(100),
    contacto_email      VARCHAR(120),
    contacto_telefono   VARCHAR(20),
    ciudad              VARCHAR(60),
    departamento        VARCHAR(60),
    pais                VARCHAR(50)  DEFAULT 'Perú',
    fecha_alta          DATE         NOT NULL,
    estado              VARCHAR(20)  NOT NULL DEFAULT 'ACTIVO',  -- ACTIVO | INACTIVO | SUSPENDIDO
    nps_score           SMALLINT,    -- Net Promoter Score 0-10
    gerente_cuenta      VARCHAR(100),
    created_at          TIMESTAMPTZ  DEFAULT NOW(),
    updated_at          TIMESTAMPTZ  DEFAULT NOW()
);

-- Insertar 50 clientes corporativos representativos del mercado peruano
-- (en producción habría 1000+; se usa generate_series para completar)
INSERT INTO b2b_crm.clientes
    (ruc, razon_social, nombre_comercial, sector, segmento, contacto_nombre,
     contacto_email, contacto_telefono, ciudad, departamento, fecha_alta, estado, nps_score, gerente_cuenta)
VALUES
    ('20100053455', 'BANCO DE CREDITO DEL PERU S.A.', 'BCP',                       'Financiero',        'ENTERPRISE', 'Carlos Mendoza',     'c.mendoza@bcp.com.pe',        '+51 1 313-2000', 'Lima',          'Lima',         '2015-03-01', 'ACTIVO',    9,  'Ana Torres'),
    ('20131565659', 'INTERBANK S.A.',                 'Interbank',                   'Financiero',        'ENTERPRISE', 'María Quispe',        'm.quispe@interbank.pe',        '+51 1 219-2000', 'Lima',          'Lima',         '2016-07-15', 'ACTIVO',    8,  'Luis Vargas'),
    ('20100055580', 'CLARO PERU S.A.C.',              'Claro',                       'Telecomunicaciones','ENTERPRISE', 'Pedro Huanca',        'p.huanca@claro.com.pe',        '+51 1 900-9900', 'Lima',          'Lima',         '2014-01-10', 'ACTIVO',    7,  'Ana Torres'),
    ('20341439308', 'SAGA FALABELLA S.A.',            'Falabella',                   'Retail',            'ENTERPRISE', 'Lucía Paredes',       'l.paredes@falabella.com.pe',   '+51 1 616-0000', 'Lima',          'Lima',         '2017-05-20', 'ACTIVO',    8,  'Carlos Ríos'),
    ('20492092313', 'SUPERMERCADOS PERUANOS S.A.',    'Plaza Vea',                   'Retail',            'ENTERPRISE', 'Roberto Salinas',     'r.salinas@spsa.com.pe',        '+51 1 625-0000', 'Lima',          'Lima',         '2018-02-14', 'ACTIVO',    7,  'Luis Vargas'),
    ('20100017491', 'PETROPERU S.A.',                 'PetroPeru',                   'Energía',           'GOBIERNO',   'Fernando Castro',     'f.castro@petroperu.com.pe',    '+51 1 330-7000', 'Lima',          'Lima',         '2013-09-01', 'ACTIVO',    6,  'Ana Torres'),
    ('20132372795', 'ALICORP SAA',                    'Alicorp',                     'Manufactura',       'ENTERPRISE', 'Sandra Chávez',       's.chavez@alicorp.com.pe',      '+51 1 315-0800', 'Lima',          'Lima',         '2015-11-30', 'ACTIVO',    9,  'Carlos Ríos'),
    ('20100105862', 'UNION DE CERVECERIAS PERUANAS BACKUS Y JOHNSTON SAA', 'Backus', 'Manufactura',       'ENTERPRISE', 'Javier Morales',      'j.morales@backus.pe',          '+51 1 213-5000', 'Lima',          'Lima',         '2016-04-18', 'ACTIVO',    8,  'Luis Vargas'),
    ('20518948499', 'ENTEL PERU S.A.',                'Entel',                       'Telecomunicaciones','ENTERPRISE', 'Patricia Flores',     'p.flores@entel.pe',            '+51 1 900-3636', 'Lima',          'Lima',         '2019-01-07', 'ACTIVO',    7,  'Ana Torres'),
    ('20600695771', 'BITEL S.A.C.',                   'Bitel',                       'Telecomunicaciones','ENTERPRISE', 'Miguel Soto',         'm.soto@bitel.com.pe',          '+51 1 900-7000', 'Lima',          'Lima',         '2019-06-15', 'ACTIVO',    6,  'Carlos Ríos'),
    ('20159420198', 'RIMAC SEGUROS Y REASEGUROS',     'Rimac Seguros',               'Seguros',           'ENTERPRISE', 'Gloria Ramirez',      'g.ramirez@rimac.com.pe',       '+51 1 411-3000', 'Lima',          'Lima',         '2015-08-22', 'ACTIVO',    8,  'Luis Vargas'),
    ('20100022648', 'PACIFICO COMPANIA DE SEGUROS',   'Pacífico Seguros',            'Seguros',           'ENTERPRISE', 'Héctor Gutiérrez',    'h.gutierrez@pacifico.com.pe',  '+51 1 513-5000', 'Lima',          'Lima',         '2016-12-01', 'ACTIVO',    7,  'Ana Torres'),
    ('20301861389', 'RANSA COMERCIAL S.A.',           'Ransa Logística',             'Logística',         'ENTERPRISE', 'Carmen Vega',         'c.vega@ransa.net',             '+51 1 618-0000', 'Callao',        'Callao',       '2017-03-10', 'ACTIVO',    8,  'Carlos Ríos'),
    ('20510182563', 'CORPORACION GRAFICA NAVARRETE',  'Navarrete',                   'Editorial',         'PYME',       'Andrés León',         'a.leon@navarrete.com.pe',      '+51 1 200-1000', 'Lima',          'Lima',         '2020-01-15', 'ACTIVO',    7,  'Luis Vargas'),
    ('20601233488', 'INNOVA SCHOOLS S.A.C.',          'Innova Schools',              'Educación',         'ENTERPRISE', 'Gabriela Ponce',      'g.ponce@innovaschools.edu.pe', '+51 1 700-1000', 'Lima',          'Lima',         '2018-08-01', 'ACTIVO',    9,  'Ana Torres'),
    ('20508565934', 'GRUPO ROMERO S.A.A.',            'Grupo Romero',                'Conglomerado',      'ENTERPRISE', 'Ricardo Bustamante',  'r.bustamante@gruporomero.pe',  '+51 1 205-4000', 'Lima',          'Lima',         '2014-05-20', 'ACTIVO',    8,  'Carlos Ríos'),
    ('20100897318', 'CENCOSUD RETAIL PERU SA',        'Metro / Wong',                'Retail',            'ENTERPRISE', 'Isabel Mendívil',     'i.mendivil@cencosud.com',      '+51 1 618-2020', 'Lima',          'Lima',         '2016-09-30', 'ACTIVO',    7,  'Luis Vargas'),
    ('20418108151', 'EDEGEL S.A.A.',                  'Enel Generación',             'Energía',           'ENTERPRISE', 'Rodrigo Palomino',    'r.palomino@enelgeneracion.pe', '+51 1 206-8000', 'Lima',          'Lima',         '2015-02-28', 'ACTIVO',    6,  'Ana Torres'),
    ('20337564373', 'ELECTRONORTE S.A.',              'Electronorte',                'Energía',           'GOBIERNO',   'Diana Zuñiga',        'd.zuniga@electronorte.com.pe', '+51 74 20-0000', 'Chiclayo',      'Lambayeque',   '2018-04-12', 'ACTIVO',    6,  'Carlos Ríos'),
    ('20503503639', 'ELECTRO ORIENTE S.A.',           'Electro Oriente',             'Energía',           'GOBIERNO',   'Eduardo Cáceres',     'e.caceres@elor.com.pe',        '+51 65 25-0000', 'Iquitos',       'Loreto',       '2019-07-01', 'ACTIVO',    5,  'Luis Vargas'),
    ('20126497737', 'SOUTHERN PERU COPPER CORPORATION','Southern Copper',             'Minería',           'ENTERPRISE', 'Alfredo Salas',       'a.salas@southernperu.com',     '+51 54 20-3000', 'Arequipa',      'Arequipa',     '2013-01-15', 'ACTIVO',    7,  'Ana Torres'),
    ('20170854771', 'COMPANIA MINERA ANTAPACCAY SA',  'Antapaccay',                  'Minería',           'ENTERPRISE', 'Sylvia Cornejo',      's.cornejo@antapaccay.com.pe',  '+51 84 80-0000', 'Cusco',         'Cusco',        '2016-11-08', 'ACTIVO',    8,  'Carlos Ríos'),
    ('20100088963', 'SCOTIABANK PERU S.A.A.',         'Scotiabank',                  'Financiero',        'ENTERPRISE', 'Marcos Valdivia',     'm.valdivia@scotiabank.com.pe', '+51 1 211-6000', 'Lima',          'Lima',         '2015-06-01', 'ACTIVO',    8,  'Luis Vargas'),
    ('20555530079', 'MIBANCO BANCO DE LA MICROEMPRESA','MiBanco',                    'Financiero',        'ENTERPRISE', 'Rosa Atauje',         'r.atauje@mibanco.com.pe',      '+51 1 319-5000', 'Lima',          'Lima',         '2017-09-20', 'ACTIVO',    7,  'Ana Torres'),
    ('20601815890', 'YAPE S.A.C.',                    'Yape',                        'Fintech',           'ENTERPRISE', 'Diego Huamán',        'd.huaman@yape.com.pe',          '+51 1 313-2500', 'Lima',          'Lima',         '2020-03-01', 'ACTIVO',    9,  'Carlos Ríos'),
    ('20605396104', 'CULQI S.A.C.',                   'Culqi',                       'Fintech',           'PYME',       'Valeria Espinoza',    'v.espinoza@culqi.com',         '+51 1 700-5000', 'Lima',          'Lima',         '2021-01-10', 'ACTIVO',    8,  'Luis Vargas'),
    ('20601022047', 'RAPPI PERU S.R.L.',              'Rappi',                       'E-Commerce',        'ENTERPRISE', 'Santiago Bermúdez',   's.bermudez@rappi.com',          '+51 1 500-0500', 'Lima',          'Lima',         '2019-11-15', 'ACTIVO',    6,  'Ana Torres'),
    ('20509706443', 'UNIVERSIDAD PERUANA DE CIENCIAS APLICADAS SAC','UPC',           'Educación',         'ENTERPRISE', 'Claudia Moreno',      'c.moreno@upc.edu.pe',          '+51 1 313-3000', 'Lima',          'Lima',         '2016-03-01', 'ACTIVO',    8,  'Carlos Ríos'),
    ('20329799684', 'PONTIFICIA UNIVERSIDAD CATOLICA DEL PERU','PUCP',               'Educación',         'GOBIERNO',   'José Aquino',         'j.aquino@pucp.edu.pe',         '+51 1 626-2000', 'Lima',          'Lima',         '2015-04-15', 'ACTIVO',    9,  'Luis Vargas'),
    ('20600867893', 'CLINICA INTERNACIONAL S.A.',     'Clínica Internacional',       'Salud',             'ENTERPRISE', 'Nadia Bermejo',       'n.bermejo@clinicainternacional.pe','+51 1 619-6161','Lima',        'Lima',         '2018-06-01', 'ACTIVO',    8,  'Ana Torres'),
    ('20297939131', 'CLINICA RICARDO PALMA S.A.',     'Clínica Ricardo Palma',       'Salud',             'ENTERPRISE', 'Cesar Quiroga',       'c.quiroga@crp.com.pe',         '+51 1 224-2224', 'Lima',          'Lima',         '2017-10-12', 'ACTIVO',    7,  'Carlos Ríos'),
    ('20461435890', 'SOCIEDAD ELECTRICA DEL SUR OESTE','SEAL',                       'Energía',           'GOBIERNO',   'Hugo Delgado',        'h.delgado@seal.com.pe',        '+51 54 38-1818', 'Arequipa',      'Arequipa',     '2016-08-20', 'ACTIVO',    6,  'Luis Vargas'),
    ('20601352106', 'CAJA RURAL DE AHORRO Y CREDITO RAIZ','Caja Raíz',               'Financiero',        'PYME',       'Fiorella Nava',       'f.nava@cajaraiz.com.pe',       '+51 1 200-7010', 'Lima',          'Lima',         '2020-09-01', 'ACTIVO',    7,  'Ana Torres'),
    ('20600399336', 'BSALE PERU S.A.C.',              'BSale',                       'Software',          'PYME',       'Renata Guzmán',       'r.guzman@bsale.pe',            '+51 1 500-0600', 'Lima',          'Lima',         '2021-05-15', 'ACTIVO',    8,  'Carlos Ríos'),
    ('20601667805', 'JOINNUS S.A.C.',                 'Joinnus',                     'Tecnología',        'PYME',       'Bruno Yrigoyen',      'b.yrigoyen@joinnus.com',        '+51 1 500-0700', 'Lima',          'Lima',         '2021-08-20', 'ACTIVO',    7,  'Luis Vargas'),
    ('20555196630', 'GRUPO BRECA',                    'Breca',                       'Conglomerado',      'ENTERPRISE', 'Alvaro Benavides',    'a.benavides@breca.com.pe',     '+51 1 619-0000', 'Lima',          'Lima',         '2014-12-01', 'ACTIVO',    8,  'Ana Torres'),
    ('20512092279', 'CONSORCIO TRANSMANTARO S.A.',    'CTM',                         'Energía',           'ENTERPRISE', 'Patricia Zegarra',    'p.zegarra@ctm.com.pe',         '+51 1 617-5000', 'Lima',          'Lima',         '2015-07-15', 'ACTIVO',    7,  'Carlos Ríos'),
    ('20602561884', 'AMAZON WEB SERVICES PERU SRL',   'AWS Peru',                    'Cloud',             'ENTERPRISE', 'Thomas Wong',         't.wong@aws.amazon.com',         '+51 1 700-0000', 'Lima',          'Lima',         '2022-01-01', 'ACTIVO',    9,  'Luis Vargas'),
    ('20601936052', 'MICROSOFT PERU S.R.L.',          'Microsoft Peru',              'Software',          'ENTERPRISE', 'Laura Huertas',       'l.huertas@microsoft.com',       '+51 1 613-7000', 'Lima',          'Lima',         '2016-02-28', 'ACTIVO',    8,  'Ana Torres'),
    ('20505557411', 'IBM DEL PERU S.A.C.',            'IBM Peru',                    'Tecnología',        'ENTERPRISE', 'Vicente Zapata',      'v.zapata@ibm.com',              '+51 1 215-0000', 'Lima',          'Lima',         '2013-06-10', 'ACTIVO',    7,  'Carlos Ríos'),
    ('20552234442', 'ORACLE DEL PERU S.A.C.',         'Oracle Peru',                 'Software',          'ENTERPRISE', 'Beatriz Solano',      'b.solano@oracle.com',           '+51 1 612-0000', 'Lima',          'Lima',         '2014-10-15', 'ACTIVO',    7,  'Luis Vargas'),
    ('20345678901', 'GOBIERNO REGIONAL AREQUIPA',     'GR Arequipa',                 'Gobierno',          'GOBIERNO',   'Marco Apaza',         'm.apaza@regionarequipa.gob.pe', '+51 54 27-0000', 'Arequipa',      'Arequipa',     '2018-01-15', 'ACTIVO',    5,  'Ana Torres'),
    ('20456789012', 'MUNICIPALIDAD DE MIRAFLORES',    'Municipio Miraflores',        'Gobierno',          'GOBIERNO',   'Pilar Torres',        'p.torres@miraflores.gob.pe',   '+51 1 617-7272', 'Lima',          'Lima',         '2019-03-01', 'ACTIVO',    7,  'Carlos Ríos'),
    ('20567890123', 'MINISTERIO DE SALUD',            'MINSA',                       'Gobierno',          'GOBIERNO',   'Juan Condori',        'j.condori@minsa.gob.pe',       '+51 1 315-6600', 'Lima',          'Lima',         '2017-07-28', 'ACTIVO',    6,  'Luis Vargas'),
    ('20678901234', 'SUNAFIL',                        'SUNAFIL',                     'Gobierno',          'GOBIERNO',   'Ana Ccama',           'a.ccama@sunafil.gob.pe',       '+51 1 391-7888', 'Lima',          'Lima',         '2020-06-15', 'ACTIVO',    6,  'Ana Torres'),
    ('20789012345', 'TELETICA PERU S.A.C.',           'Teletica',                    'Media',             'PYME',       'Oscar Ramos',         'o.ramos@teletica.pe',           '+51 1 500-0800', 'Lima',          'Lima',         '2022-03-10', 'ACTIVO',    7,  'Carlos Ríos'),
    ('20890123456', 'INKASUR S.A.C.',                 'InkaSur',                     'Manufactura',       'PYME',       'Milagros Inca',       'm.inca@inkasur.pe',             '+51 54 42-0000', 'Arequipa',      'Arequipa',     '2021-10-01', 'ACTIVO',    6,  'Luis Vargas'),
    ('20901234567', 'TRANSPORTES LINEA S.A.',         'Línea',                       'Transporte',        'ENTERPRISE', 'Arturo Lara',         'a.lara@linea.com.pe',           '+51 44 24-0000', 'Trujillo',      'La Libertad',  '2018-11-20', 'ACTIVO',    7,  'Ana Torres'),
    ('20012345678', 'CAMPOSOL S.A.',                  'Camposol',                    'Agroindustria',     'ENTERPRISE', 'Elena Rojas',         'e.rojas@camposol.com',          '+51 44 48-0000', 'Trujillo',      'La Libertad',  '2017-02-14', 'ACTIVO',    8,  'Carlos Ríos'),
    ('20123456780', 'AJE GROUP S.A.C.',               'AJE Group',                   'Manufactura',       'ENTERPRISE', 'Daniel Añaños',       'd.ananos@ajegroup.com',         '+51 1 618-4646', 'Lima',          'Lima',         '2016-06-30', 'ACTIVO',    7,  'Luis Vargas');

-- Generar clientes adicionales con generate_series para alcanzar 1000+
INSERT INTO b2b_crm.clientes
    (ruc, razon_social, nombre_comercial, sector, segmento, contacto_nombre,
     contacto_email, ciudad, departamento, fecha_alta, estado, nps_score, gerente_cuenta)
SELECT
    -- RUC sintético de 11 dígitos
    LPAD((20000000000 + gs)::TEXT, 11, '0'),
    'EMPRESA CORPORATIVA ' || gs || ' S.A.C.',
    'Corp-' || gs,
    (ARRAY['Telecomunicaciones','Financiero','Retail','Manufactura','Energía',
            'Logística','Educación','Salud','Tecnología','Gobierno'])[1 + (gs % 10)],
    (ARRAY['ENTERPRISE','PYME','GOBIERNO'])[1 + (gs % 3)],
    'Contacto ' || gs,
    'contacto' || gs || '@empresa' || gs || '.pe',
    (ARRAY['Lima','Arequipa','Trujillo','Chiclayo','Piura','Iquitos','Cusco','Tacna'])[1 + (gs % 8)],
    (ARRAY['Lima','Arequipa','La Libertad','Lambayeque','Piura','Loreto','Cusco','Tacna'])[1 + (gs % 8)],
    DATE '2018-01-01' + (gs % 1800) * INTERVAL '1 day',
    (ARRAY['ACTIVO','ACTIVO','ACTIVO','ACTIVO','INACTIVO','SUSPENDIDO'])[1 + (gs % 6)],
    5 + (gs % 6),
    (ARRAY['Ana Torres','Luis Vargas','Carlos Ríos'])[1 + (gs % 3)]
FROM generate_series(1, 950) AS gs;

-- -----------------------------------------------------------------------------
-- Tabla: b2b_crm.contratos
-- Contratos de servicios B2B vigentes y cerrados
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS b2b_crm.contratos (
    id                  SERIAL PRIMARY KEY,
    numero_contrato     VARCHAR(30)  NOT NULL UNIQUE,
    cliente_id          INTEGER      NOT NULL REFERENCES b2b_crm.clientes(id),
    tipo_servicio       VARCHAR(80)  NOT NULL,
    descripcion         TEXT,
    monto_mensual_usd   NUMERIC(12,2) NOT NULL,
    sla_uptime_pct      NUMERIC(5,2) DEFAULT 99.9,
    fecha_inicio        DATE         NOT NULL,
    fecha_vencimiento   DATE         NOT NULL,
    estado              VARCHAR(20)  NOT NULL DEFAULT 'VIGENTE',  -- VIGENTE | VENCIDO | CANCELADO | EN_NEGOCIACION
    renovacion_auto     BOOLEAN      DEFAULT TRUE,
    cuenta_gestor       VARCHAR(100),
    created_at          TIMESTAMPTZ  DEFAULT NOW()
);

-- Insertar contratos base para los 50 clientes nombrados
INSERT INTO b2b_crm.contratos
    (numero_contrato, cliente_id, tipo_servicio, descripcion,
     monto_mensual_usd, sla_uptime_pct, fecha_inicio, fecha_vencimiento, estado, cuenta_gestor)
VALUES
    ('CTR-2024-00001', 1,  'MPLS Corporativo',         'Red MPLS Premium 500 Mbps Lima-Provincias',        8500.00,  99.95, '2024-01-01', '2026-12-31', 'VIGENTE',          'Ana Torres'),
    ('CTR-2024-00002', 1,  'SD-WAN Enterprise',        'SD-WAN con 25 sucursales, QoS avanzado',           12000.00, 99.99, '2024-03-01', '2026-02-28', 'VIGENTE',          'Ana Torres'),
    ('CTR-2023-00015', 2,  'MPLS Corporativo',         'Red MPLS 200 Mbps con backup 4G',                  4200.00,  99.9,  '2023-06-01', '2025-05-31', 'VIGENTE',          'Luis Vargas'),
    ('CTR-2024-00008', 2,  'DRaaS - Disaster Recovery','Plan DRaaS Tier 2 - RPO 4h / RTO 8h',             6800.00,  99.9,  '2024-02-01', '2026-01-31', 'VIGENTE',          'Luis Vargas'),
    ('CTR-2022-00033', 3,  'Cloud Hosting Premium',    'Hosting en cloud privado: 20 VMs, 40 TB SAN',     18000.00, 99.99, '2022-09-01', '2024-08-31', 'VENCIDO',          'Ana Torres'),
    ('CTR-2024-00019', 3,  'Cloud Hosting Premium',    'Renovación cloud privado: 25 VMs, 60 TB SAN',     22000.00, 99.99, '2024-09-01', '2026-08-31', 'VIGENTE',          'Ana Torres'),
    ('CTR-2024-00022', 4,  'SD-WAN Enterprise',        'SD-WAN 50 tiendas retail, failover automático',   15500.00, 99.9,  '2024-04-15', '2026-04-14', 'VIGENTE',          'Carlos Ríos'),
    ('CTR-2024-00031', 5,  'MPLS Corporativo',         'MPLS 150 Mbps - Red distribución nacional',       5800.00,  99.9,  '2024-01-20', '2025-01-19', 'VIGENTE',          'Luis Vargas'),
    ('CTR-2023-00044', 6,  'FTTH Empresarial',         'Fibra óptica empresarial 1 Gbps simétrico',       3200.00,  99.5,  '2023-11-01', '2025-10-31', 'VIGENTE',          'Ana Torres'),
    ('CTR-2024-00040', 7,  'Cloud Hosting Premium',    '10 VMs en cloud híbrido, backup diario a S3',     9500.00,  99.95, '2024-06-01', '2026-05-31', 'VIGENTE',          'Carlos Ríos'),
    ('CTR-2024-00041', 8,  'SD-WAN Enterprise',        'SD-WAN 30 plantas de producción',                 11200.00, 99.9,  '2024-07-01', '2026-06-30', 'VIGENTE',          'Luis Vargas'),
    ('CTR-2023-00050', 9,  'MPLS Corporativo',         'MPLS 300 Mbps backbone Lima-Provincias',          7800.00,  99.95, '2023-12-01', '2025-11-30', 'VIGENTE',          'Ana Torres'),
    ('CTR-2024-00055', 10, 'FTTH Empresarial',         'Fibra 500 Mbps con IP fija dedicada',             2800.00,  99.5,  '2024-02-15', '2025-02-14', 'VIGENTE',          'Carlos Ríos'),
    ('CTR-2023-00060', 11, 'DRaaS - Disaster Recovery','Plan DRaaS Tier 1 - RPO 1h / RTO 2h',            15000.00, 99.99, '2023-08-01', '2025-07-31', 'VIGENTE',          'Luis Vargas'),
    ('CTR-2024-00070', 12, 'DRaaS - Disaster Recovery','Plan DRaaS Tier 2 con replicación de BD',         9500.00,  99.9,  '2024-01-01', '2025-12-31', 'VIGENTE',          'Ana Torres'),
    ('CTR-2022-00080', 13, 'Cloud Hosting Premium',    'Logística cloud: 15 VMs + 80 TB almacenamiento',  14000.00, 99.95, '2022-05-01', '2024-04-30', 'VENCIDO',          'Carlos Ríos'),
    ('CTR-2024-00081', 13, 'Cloud Hosting Premium',    'Renovación logística: 18 VMs + 100 TB',          16500.00, 99.95, '2024-05-01', '2026-04-30', 'VIGENTE',          'Carlos Ríos'),
    ('CTR-2024-00090', 14, 'MPLS Corporativo',         'MPLS 50 Mbps - red editorial',                    1800.00,  99.5,  '2024-03-01', '2025-02-28', 'VIGENTE',          'Luis Vargas'),
    ('CTR-2024-00100', 15, 'SD-WAN Enterprise',        'SD-WAN 120 colegios - gestión centralizada',      38000.00, 99.9,  '2024-01-15', '2026-01-14', 'VIGENTE',          'Ana Torres'),
    ('CTR-2023-00110', 16, 'Cloud Hosting Premium',    'Cloud privado conglomerado: 50 VMs + DR',         35000.00, 99.99, '2023-03-01', '2026-02-28', 'VIGENTE',          'Carlos Ríos');

-- Generar contratos adicionales para alcanzar 500+
INSERT INTO b2b_crm.contratos
    (numero_contrato, cliente_id, tipo_servicio, descripcion,
     monto_mensual_usd, sla_uptime_pct, fecha_inicio, fecha_vencimiento, estado, cuenta_gestor)
SELECT
    'CTR-' || EXTRACT(YEAR FROM (DATE '2022-01-01' + (gs % 900) * INTERVAL '1 day'))::TEXT ||
    '-' || LPAD((200 + gs)::TEXT, 5, '0'),
    1 + (gs % 50),  -- Distribuir entre los 50 clientes base
    (ARRAY['MPLS Corporativo','SD-WAN Enterprise','Cloud Hosting Premium',
            'DRaaS - Disaster Recovery','FTTH Empresarial','Internet Dedicado',
            'VPN Gestionada','Colocation Premium'])[1 + (gs % 8)],
    'Servicio gestionado - contrato generado automáticamente para cliente ' || (1 + (gs % 50)),
    (500 + (gs * 137 % 40000))::NUMERIC / 100.0,
    (ARRAY[99.5, 99.9, 99.95, 99.99])[1 + (gs % 4)],
    DATE '2022-01-01' + (gs % 900) * INTERVAL '1 day',
    DATE '2024-01-01' + (gs % 900) * INTERVAL '1 day' + INTERVAL '24 months',
    (ARRAY['VIGENTE','VIGENTE','VIGENTE','VENCIDO','CANCELADO','EN_NEGOCIACION'])[1 + (gs % 6)],
    (ARRAY['Ana Torres','Luis Vargas','Carlos Ríos'])[1 + (gs % 3)]
FROM generate_series(1, 480) AS gs;

-- -----------------------------------------------------------------------------
-- Tabla: b2b_crm.servicios_contratados
-- Detalle de servicios activos por contrato
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS b2b_crm.servicios_contratados (
    id              SERIAL PRIMARY KEY,
    contrato_id     INTEGER     NOT NULL REFERENCES b2b_crm.contratos(id),
    codigo_servicio VARCHAR(30) NOT NULL,
    nombre_servicio VARCHAR(120) NOT NULL,
    cantidad        INTEGER     NOT NULL DEFAULT 1,
    precio_unitario NUMERIC(10,2) NOT NULL,
    unidad_medida   VARCHAR(30),
    activo          BOOLEAN     DEFAULT TRUE,
    fecha_activacion DATE       NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO b2b_crm.servicios_contratados
    (contrato_id, codigo_servicio, nombre_servicio, cantidad, precio_unitario, unidad_medida, fecha_activacion)
SELECT
    1 + (gs % (SELECT COUNT(*) FROM b2b_crm.contratos)::INTEGER),
    'SVC-' || LPAD(gs::TEXT, 6, '0'),
    (ARRAY[
        'Ancho de Banda Dedicado','Backup Gestionado','Monitoreo 24x7','Soporte Nivel 2',
        'Replicación de Datos','Balanceo de Carga','Firewall Gestionado','VPN Site-to-Site',
        'CDN Empresarial','Almacenamiento SAN','DR Activo-Activo','IP Fija Dedicada'
    ])[1 + (gs % 12)],
    1 + (gs % 20),
    (100 + gs * 17 % 5000)::NUMERIC / 100.0,
    (ARRAY['Mbps','GB','Unidad','Sitio','IP','VM'])[1 + (gs % 6)],
    DATE '2022-01-01' + (gs % 1500) * INTERVAL '1 day'
FROM generate_series(1, 500) AS gs;

-- -----------------------------------------------------------------------------
-- Tabla: b2b_crm.tickets_soporte
-- Tickets de soporte técnico de clientes
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS b2b_crm.tickets_soporte (
    id              SERIAL PRIMARY KEY,
    numero_ticket   VARCHAR(20)  NOT NULL UNIQUE,
    cliente_id      INTEGER      NOT NULL REFERENCES b2b_crm.clientes(id),
    contrato_id     INTEGER      REFERENCES b2b_crm.contratos(id),
    categoria       VARCHAR(60)  NOT NULL,
    prioridad       VARCHAR(10)  NOT NULL,  -- P1 | P2 | P3 | P4
    asunto          TEXT         NOT NULL,
    descripcion     TEXT,
    canal_apertura  VARCHAR(30)  DEFAULT 'Portal',
    estado          VARCHAR(20)  NOT NULL DEFAULT 'ABIERTO',
    tiempo_respuesta_h NUMERIC(6,2),  -- Tiempo hasta primera respuesta en horas
    tiempo_resolucion_h NUMERIC(8,2), -- Tiempo hasta resolución en horas
    tecnico_asignado VARCHAR(100),
    fecha_apertura  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    fecha_cierre    TIMESTAMPTZ,
    sla_cumplido    BOOLEAN,
    created_at      TIMESTAMPTZ  DEFAULT NOW()
);

INSERT INTO b2b_crm.tickets_soporte
    (numero_ticket, cliente_id, contrato_id, categoria, prioridad, asunto,
     canal_apertura, estado, tiempo_respuesta_h, tiempo_resolucion_h,
     tecnico_asignado, fecha_apertura, fecha_cierre, sla_cumplido)
SELECT
    'TKT-' || LPAD((2024000 + gs)::TEXT, 10, '0'),
    1 + (gs % 50),
    1 + (gs % 100),
    (ARRAY['Conectividad','Rendimiento','Facturación','Configuración',
            'Incidente de Seguridad','Solicitud de Cambio','Consulta Técnica'])[1 + (gs % 7)],
    (ARRAY['P1','P2','P2','P3','P3','P4','P4'])[1 + (gs % 7)],
    'Problema reportado - ' || (ARRAY['Sin conectividad','Latencia alta','Error de factura',
        'Reconfiguración SD-WAN','Alerta de seguridad','Solicitud ampliación BW',
        'Consulta sobre SLA','Fallo de backup','Enlace MPLS degradado'])[1 + (gs % 9)],
    (ARRAY['Portal','Teléfono','Email','Teams'])[1 + (gs % 4)],
    (ARRAY['ABIERTO','EN_PROGRESO','RESUELTO','CERRADO','CERRADO'])[1 + (gs % 5)],
    ROUND((0.5 + (gs % 120)::NUMERIC / 10.0), 2),
    CASE WHEN gs % 5 < 3 THEN ROUND((1.0 + (gs % 480)::NUMERIC / 10.0), 2) ELSE NULL END,
    (ARRAY['Ing. Rodríguez','Ing. García','Ing. Mamani','Ing. Sulca','Ing. Huanca'])[1 + (gs % 5)],
    NOW() - ((gs % 365) * INTERVAL '1 day') - ((gs % 24) * INTERVAL '1 hour'),
    CASE WHEN gs % 5 >= 2 THEN NOW() - ((gs % 300) * INTERVAL '1 hour') ELSE NULL END,
    (gs % 10) > 2  -- ~70% de SLA cumplido
FROM generate_series(1, 700) AS gs;

-- -----------------------------------------------------------------------------
-- Tabla: b2b_crm.facturacion
-- Registros de facturación mensual por contrato
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS b2b_crm.facturacion (
    id                  SERIAL PRIMARY KEY,
    numero_factura      VARCHAR(30)  NOT NULL UNIQUE,
    contrato_id         INTEGER      NOT NULL REFERENCES b2b_crm.contratos(id),
    cliente_id          INTEGER      NOT NULL REFERENCES b2b_crm.clientes(id),
    periodo_mes         INTEGER      NOT NULL,   -- 1-12
    periodo_anio        INTEGER      NOT NULL,
    monto_base_usd      NUMERIC(12,2) NOT NULL,
    descuento_pct       NUMERIC(5,2)  DEFAULT 0.00,
    recargo_pct         NUMERIC(5,2)  DEFAULT 0.00,
    monto_total_usd     NUMERIC(12,2) NOT NULL,
    estado_pago         VARCHAR(20)  NOT NULL DEFAULT 'PENDIENTE',
    fecha_emision       DATE         NOT NULL,
    fecha_vencimiento   DATE         NOT NULL,
    fecha_pago          DATE,
    metodo_pago         VARCHAR(40),
    created_at          TIMESTAMPTZ  DEFAULT NOW()
);

INSERT INTO b2b_crm.facturacion
    (numero_factura, contrato_id, cliente_id, periodo_mes, periodo_anio,
     monto_base_usd, descuento_pct, recargo_pct, monto_total_usd,
     estado_pago, fecha_emision, fecha_vencimiento, fecha_pago, metodo_pago)
SELECT
    'FAC-' || LPAD((2024 * 1000000 + gs)::TEXT, 13, '0'),
    1 + (gs % 100),
    1 + (gs % 50),
    1 + (gs % 12),
    2024 + (gs % 3),
    (1500 + gs * 31 % 50000)::NUMERIC / 100.0,
    CASE WHEN gs % 10 = 0 THEN 5.00 WHEN gs % 5 = 0 THEN 10.00 ELSE 0.00 END,
    CASE WHEN gs % 20 = 0 THEN 2.50 ELSE 0.00 END,
    ROUND(((1500 + gs * 31 % 50000)::NUMERIC / 100.0) * (1 - CASE WHEN gs % 10 = 0 THEN 0.05 WHEN gs % 5 = 0 THEN 0.10 ELSE 0.00 END) * (1 + CASE WHEN gs % 20 = 0 THEN 0.025 ELSE 0.00 END), 2),
    (ARRAY['PAGADO','PAGADO','PAGADO','PENDIENTE','VENCIDO'])[1 + (gs % 5)],
    DATE '2024-01-01' + ((gs % 365)) * INTERVAL '1 day',
    DATE '2024-01-31' + ((gs % 365)) * INTERVAL '1 day',
    CASE WHEN gs % 5 < 3 THEN DATE '2024-01-15' + ((gs % 365)) * INTERVAL '1 day' ELSE NULL END,
    (ARRAY['Transferencia Bancaria','Débito Automático','Cheque','Efectivo'])[1 + (gs % 4)]
FROM generate_series(1, 600) AS gs;


-- =============================================================================
-- SCHEMA: telecomunicaciones
-- Gestión de infraestructura de red, equipos y mediciones de rendimiento
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS telecomunicaciones;

-- -----------------------------------------------------------------------------
-- Tabla: telecomunicaciones.equipos_red
-- Inventario de equipos de red activos en la red del operador
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS telecomunicaciones.equipos_red (
    id              SERIAL PRIMARY KEY,
    hostname        VARCHAR(60)  NOT NULL UNIQUE,
    tipo_equipo     VARCHAR(40)  NOT NULL,  -- ROUTER_CORE | SWITCH_AGG | FIREWALL | etc.
    fabricante      VARCHAR(40),
    modelo          VARCHAR(60),
    version_os      VARCHAR(40),
    ip_gestion      INET         NOT NULL,
    ubicacion_pop   VARCHAR(80),
    ciudad          VARCHAR(40),
    rol             VARCHAR(30),  -- CORE | AGGREGATION | EDGE | CPE
    estado          VARCHAR(20)  DEFAULT 'ACTIVO',
    fecha_instalacion DATE,
    garantia_hasta  DATE,
    created_at      TIMESTAMPTZ  DEFAULT NOW()
);

INSERT INTO telecomunicaciones.equipos_red
    (hostname, tipo_equipo, fabricante, modelo, version_os, ip_gestion,
     ubicacion_pop, ciudad, rol, estado, fecha_instalacion)
VALUES
    ('rt-core-lima-01',      'ROUTER_CORE',  'Cisco',     'ASR9001',      'IOS-XR 7.7.1', '10.0.0.1',   'POP Lima Centro',   'Lima',      'CORE',        'ACTIVO', '2020-03-15'),
    ('rt-core-lima-02',      'ROUTER_CORE',  'Cisco',     'ASR9001',      'IOS-XR 7.7.1', '10.0.0.2',   'POP Lima Centro',   'Lima',      'CORE',        'ACTIVO', '2020-03-15'),
    ('rt-core-lima-03',      'ROUTER_CORE',  'Juniper',   'MX480',        'Junos 22.3R1',  '10.0.0.3',   'POP San Isidro',    'Lima',      'CORE',        'ACTIVO', '2021-06-01'),
    ('sw-agg-lima-01',       'SWITCH_AGG',   'Cisco',     'Nexus 9300',   'NX-OS 10.2.3', '10.0.1.1',   'POP Lima Centro',   'Lima',      'AGGREGATION', 'ACTIVO', '2020-04-01'),
    ('sw-agg-lima-02',       'SWITCH_AGG',   'Cisco',     'Nexus 9300',   'NX-OS 10.2.3', '10.0.1.2',   'POP San Isidro',    'Lima',      'AGGREGATION', 'ACTIVO', '2020-04-01'),
    ('fw-edge-lima-01',      'FIREWALL',     'Palo Alto', 'PA-5450',      'PAN-OS 11.0.1', '10.0.2.1',   'POP Lima Centro',   'Lima',      'EDGE',        'ACTIVO', '2021-01-10'),
    ('fw-edge-lima-02',      'FIREWALL',     'Palo Alto', 'PA-5450',      'PAN-OS 11.0.1', '10.0.2.2',   'POP San Isidro',    'Lima',      'EDGE',        'ACTIVO', '2021-01-10'),
    ('rt-edge-arq-01',       'ROUTER_EDGE',  'Cisco',     'ASR1002-HX',   'IOS-XE 17.9.4', '10.1.0.1',  'POP Arequipa',      'Arequipa',  'EDGE',        'ACTIVO', '2019-09-20'),
    ('rt-edge-truj-01',      'ROUTER_EDGE',  'Cisco',     'ASR1002-HX',   'IOS-XE 17.9.4', '10.2.0.1',  'POP Trujillo',      'Trujillo',  'EDGE',        'ACTIVO', '2020-01-15'),
    ('rt-edge-chic-01',      'ROUTER_EDGE',  'Juniper',   'MX204',        'Junos 22.4R2',  '10.3.0.1',   'POP Chiclayo',      'Chiclayo',  'EDGE',        'ACTIVO', '2020-07-01'),
    ('rt-edge-piura-01',     'ROUTER_EDGE',  'Cisco',     'ASR1001-X',    'IOS-XE 17.9.4', '10.4.0.1',  'POP Piura',         'Piura',     'EDGE',        'ACTIVO', '2021-03-10'),
    ('rt-edge-cusco-01',     'ROUTER_EDGE',  'Cisco',     'ASR1001-X',    'IOS-XE 17.9.4', '10.5.0.1',  'POP Cusco',         'Cusco',     'EDGE',        'ACTIVO', '2021-05-20'),
    ('sw-agg-arq-01',        'SWITCH_AGG',   'Cisco',     'Catalyst 9500','IOS-XE 17.9.4', '10.1.1.1',  'POP Arequipa',      'Arequipa',  'AGGREGATION', 'ACTIVO', '2019-10-01'),
    ('cpe-bcp-lima-01',      'CPE',          'Cisco',     'ISR4321',      'IOS-XE 17.3.6', '172.16.1.1', 'BCP Lima Centro',   'Lima',      'CPE',         'ACTIVO', '2022-01-15'),
    ('cpe-interbank-lima-01','CPE',          'Cisco',     'ISR4331',      'IOS-XE 17.3.6', '172.16.2.1', 'Interbank HQ',      'Lima',      'CPE',         'ACTIVO', '2021-08-01'),
    ('cpe-alicorp-lima-01',  'CPE',          'Cisco',     'ISR4451',      'IOS-XE 17.3.6', '172.16.3.1', 'Alicorp HQ',        'Lima',      'CPE',         'ACTIVO', '2022-03-15'),
    ('rt-core-iqt-01',       'ROUTER_CORE',  'Cisco',     'ASR1002-HX',   'IOS-XE 17.9.4', '10.6.0.1',  'POP Iquitos',       'Iquitos',   'CORE',        'ACTIVO', '2022-06-01'),
    ('sw-dist-lima-01',      'SWITCH_DIST',  'Cisco',     'Catalyst 9300','IOS-XE 17.9.4', '10.0.3.1',  'POP Lima Norte',    'Lima',      'AGGREGATION', 'ACTIVO', '2021-11-15'),
    ('lb-app-lima-01',       'BALANCEADOR',  'F5',        'BIG-IP i4600', 'TMOS 16.1.3',   '10.0.4.1',  'POP Lima Centro',   'Lima',      'EDGE',        'ACTIVO', '2020-08-20'),
    ('vpn-gw-lima-01',       'VPN_GATEWAY',  'Cisco',     'FTD 4150',     'FTD 7.2.4',     '10.0.5.1',  'POP Lima Centro',   'Lima',      'EDGE',        'ACTIVO', '2021-02-28');

-- Generar equipos CPE adicionales
INSERT INTO telecomunicaciones.equipos_red
    (hostname, tipo_equipo, fabricante, modelo, version_os, ip_gestion,
     ubicacion_pop, ciudad, rol, estado, fecha_instalacion)
SELECT
    'cpe-cliente-' || LPAD(gs::TEXT, 4, '0'),
    'CPE',
    (ARRAY['Cisco','Huawei','Juniper','MikroTik'])[1 + (gs % 4)],
    (ARRAY['ISR4321','AR2220','SRX300','CCR1009'])[1 + (gs % 4)],
    (ARRAY['IOS-XE 17.3.6','VRP V200R019','Junos 20.4R3','RouterOS 7.6'])[1 + (gs % 4)],
    ('172.20.' || (gs / 256) || '.' || (gs % 256))::INET,
    'Sitio Cliente ' || gs,
    (ARRAY['Lima','Arequipa','Trujillo','Chiclayo','Piura','Iquitos','Cusco','Tacna'])[1 + (gs % 8)],
    'CPE',
    (ARRAY['ACTIVO','ACTIVO','ACTIVO','INACTIVO'])[1 + (gs % 4)],
    DATE '2019-01-01' + (gs % 1800) * INTERVAL '1 day'
FROM generate_series(1, 80) AS gs;

-- -----------------------------------------------------------------------------
-- Tabla: telecomunicaciones.enlaces
-- Inventario de enlaces de red (MPLS, SD-WAN, Internet, Dedicado)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS telecomunicaciones.enlaces (
    id              SERIAL PRIMARY KEY,
    codigo_enlace   VARCHAR(30)  NOT NULL UNIQUE,
    tipo_enlace     VARCHAR(30)  NOT NULL,  -- MPLS | SDWAN | INTERNET | FTTH | MICROONDAS
    cliente_id      INTEGER      REFERENCES b2b_crm.clientes(id),
    equipo_a_id     INTEGER      REFERENCES telecomunicaciones.equipos_red(id),
    equipo_b_id     INTEGER      REFERENCES telecomunicaciones.equipos_red(id),
    capacidad_mbps  NUMERIC(10,2) NOT NULL,
    latencia_ms_sla NUMERIC(6,2) DEFAULT 10.0,
    jitter_ms_sla   NUMERIC(6,2) DEFAULT 5.0,
    perdida_pct_sla NUMERIC(5,2) DEFAULT 0.5,
    estado          VARCHAR(20)  DEFAULT 'ACTIVO',
    ciudad_a        VARCHAR(40),
    ciudad_b        VARCHAR(40),
    fecha_activacion DATE,
    created_at      TIMESTAMPTZ  DEFAULT NOW()
);

INSERT INTO telecomunicaciones.enlaces
    (codigo_enlace, tipo_enlace, cliente_id, equipo_a_id, equipo_b_id,
     capacidad_mbps, latencia_ms_sla, jitter_ms_sla, perdida_pct_sla,
     estado, ciudad_a, ciudad_b, fecha_activacion)
SELECT
    'ENL-' || LPAD(gs::TEXT, 6, '0'),
    (ARRAY['MPLS','SDWAN','INTERNET','FTTH','MICROONDAS','MPLS','SDWAN'])[1 + (gs % 7)],
    CASE WHEN gs % 3 = 0 THEN NULL ELSE 1 + (gs % 50) END,
    1 + (gs % 20),
    1 + ((gs + 5) % 20),
    (ARRAY[10,50,100,200,500,1000,2000,10000])[1 + (gs % 8)],
    (ARRAY[5.0, 8.0, 10.0, 15.0, 20.0, 30.0])[1 + (gs % 6)],
    (ARRAY[2.0, 3.0, 5.0, 8.0])[1 + (gs % 4)],
    (ARRAY[0.1, 0.5, 1.0])[1 + (gs % 3)],
    (ARRAY['ACTIVO','ACTIVO','ACTIVO','ACTIVO','INACTIVO','MANTENIMIENTO'])[1 + (gs % 6)],
    (ARRAY['Lima','Arequipa','Trujillo','Chiclayo','Piura','Iquitos','Cusco','Lima'])[1 + (gs % 8)],
    (ARRAY['Lima','Arequipa','Trujillo','Chiclayo','Piura','Iquitos','Cusco','Callao'])[1 + ((gs+3) % 8)],
    DATE '2019-01-01' + (gs % 1800) * INTERVAL '1 day'
FROM generate_series(1, 200) AS gs;

-- -----------------------------------------------------------------------------
-- Tabla: telecomunicaciones.mediciones_performance
-- Mediciones de rendimiento de red por enlace (telemetría)
-- ~2000 registros para tener datos de health check interesantes
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS telecomunicaciones.mediciones_performance (
    id              SERIAL PRIMARY KEY,
    enlace_id       INTEGER      NOT NULL REFERENCES telecomunicaciones.enlaces(id),
    timestamp_med   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    latencia_ms     NUMERIC(8,3) NOT NULL,
    jitter_ms       NUMERIC(8,3) NOT NULL,
    perdida_pct     NUMERIC(6,3) NOT NULL DEFAULT 0.0,
    throughput_mbps NUMERIC(10,2),
    utilizacion_pct NUMERIC(6,2),  -- % de capacidad utilizada
    rtd_ms          NUMERIC(8,3),  -- Round-Trip Delay
    mos_score       NUMERIC(4,2),  -- Mean Opinion Score para VoIP (1-5)
    created_at      TIMESTAMPTZ   DEFAULT NOW()
);

-- Insertar mediciones de las últimas 24h para todos los enlaces
INSERT INTO telecomunicaciones.mediciones_performance
    (enlace_id, timestamp_med, latencia_ms, jitter_ms, perdida_pct,
     throughput_mbps, utilizacion_pct, rtd_ms, mos_score)
SELECT
    1 + (gs % 200),
    NOW() - ((gs % 1440) * INTERVAL '1 minute'),
    -- Latencia: mayoría normal (3-15ms), algunos valores altos
    CASE
        WHEN gs % 50 = 0 THEN 80.0 + (gs % 120)  -- Pico crítico ocasional
        WHEN gs % 10 = 0 THEN 25.0 + (gs % 40)   -- Elevado
        ELSE 3.0 + (gs % 12) + (random() * 3)::NUMERIC  -- Normal
    END,
    -- Jitter: mayoría <5ms
    CASE
        WHEN gs % 30 = 0 THEN 15.0 + (gs % 25)
        ELSE 0.5 + (gs % 5) + (random() * 2)::NUMERIC
    END,
    -- Pérdida: mayoría 0%, algunos con pérdida
    CASE
        WHEN gs % 100 = 0 THEN 3.0 + (gs % 7)
        WHEN gs % 25 = 0 THEN 0.5 + (gs % 2)
        ELSE 0.0
    END,
    -- Throughput
    10.0 + (gs * 7 % 9900) / 10.0,
    -- Utilización
    5.0 + (gs % 90) + (random() * 15)::NUMERIC,
    -- RTD
    6.0 + (gs % 20),
    -- MOS Score VoIP (1-5)
    CASE
        WHEN gs % 50 = 0 THEN 1.5 + (gs % 20) / 10.0
        WHEN gs % 10 = 0 THEN 3.0 + (gs % 10) / 10.0
        ELSE 4.0 + (gs % 10) / 10.0
    END
FROM generate_series(1, 2000) AS gs;

-- -----------------------------------------------------------------------------
-- Tabla: telecomunicaciones.incidentes
-- Registro de incidentes de red con impacto en clientes
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS telecomunicaciones.incidentes (
    id                  SERIAL PRIMARY KEY,
    numero_incidente    VARCHAR(20)  NOT NULL UNIQUE,
    enlace_id           INTEGER      REFERENCES telecomunicaciones.enlaces(id),
    equipo_id           INTEGER      REFERENCES telecomunicaciones.equipos_red(id),
    cliente_id          INTEGER      REFERENCES b2b_crm.clientes(id),
    tipo_incidente      VARCHAR(60)  NOT NULL,
    severidad           VARCHAR(10)  NOT NULL,  -- S1 | S2 | S3 | S4
    descripcion         TEXT,
    causa_raiz          TEXT,
    impacto_clientes    INTEGER      DEFAULT 0,  -- Nº de clientes afectados
    duracion_minutos    INTEGER,
    estado              VARCHAR(20)  NOT NULL DEFAULT 'ACTIVO',
    tecnico_responsable VARCHAR(100),
    fecha_inicio        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    fecha_fin           TIMESTAMPTZ,
    rca_enviado         BOOLEAN      DEFAULT FALSE,
    created_at          TIMESTAMPTZ  DEFAULT NOW()
);

INSERT INTO telecomunicaciones.incidentes
    (numero_incidente, enlace_id, equipo_id, cliente_id, tipo_incidente,
     severidad, descripcion, causa_raiz, impacto_clientes, duracion_minutos,
     estado, tecnico_responsable, fecha_inicio, fecha_fin, rca_enviado)
SELECT
    'INC-' || LPAD((2024000 + gs)::TEXT, 10, '0'),
    1 + (gs % 200),
    1 + (gs % 100),
    CASE WHEN gs % 4 = 0 THEN NULL ELSE 1 + (gs % 50) END,
    (ARRAY[
        'Pérdida de enlace físico',
        'Degradación de throughput',
        'Alta latencia en enlace MPLS',
        'Fallo de equipo CPE',
        'Saturación de ancho de banda',
        'Corte de fibra óptica',
        'Fallo de alimentación UPS',
        'Ataque DDoS detectado',
        'Fallo de convergencia BGP',
        'Pérdida de ruta OSPF'
    ])[1 + (gs % 10)],
    (ARRAY['S1','S2','S2','S3','S3','S4'])[1 + (gs % 6)],
    'Incidente reportado por NOC - ' || (ARRAY[
        'Alarma SNMP en equipo de red',
        'Reporte de cliente por degradación',
        'Detección automática por monitoreo NMS',
        'Alerta de umbral de BW superado',
        'Ticket de soporte P1 escalado'
    ])[1 + (gs % 5)],
    CASE WHEN (gs % 3) = 0 THEN NULL ELSE
        (ARRAY[
            'Corte de cable de fibra por obras civiles',
            'Fallo de tarjeta de línea en equipo core',
            'Agotamiento de tabla de rutas BGP',
            'Fallo de fuente de alimentación redundante',
            'Loop de Spanning Tree no detectado a tiempo',
            'Configuración incorrecta por cambio de mantenimiento',
            'Saturación por tráfico de backup nocturno'
        ])[1 + (gs % 7)]
    END,
    gs % 50,
    CASE WHEN (gs % 5) < 4 THEN 5 + (gs % 480) ELSE NULL END,
    (ARRAY['RESUELTO','RESUELTO','RESUELTO','ACTIVO','EN_PROGRESO'])[1 + (gs % 5)],
    (ARRAY['NOC-Ing. Torres','NOC-Ing. García','NOC-Ing. Mamani','NOC-Ing. Sulca'])[1 + (gs % 4)],
    NOW() - ((gs % 720) * INTERVAL '1 hour'),
    CASE WHEN (gs % 5) < 4 THEN NOW() - ((gs % 700) * INTERVAL '1 hour') + (5 + gs % 480) * INTERVAL '1 minute' ELSE NULL END,
    (gs % 3) = 0
FROM generate_series(1, 300) AS gs;

-- =============================================================================
-- ÍNDICES para optimizar el health check
-- =============================================================================
CREATE INDEX IF NOT EXISTS idx_clientes_estado       ON b2b_crm.clientes(estado);
CREATE INDEX IF NOT EXISTS idx_contratos_estado      ON b2b_crm.contratos(estado);
CREATE INDEX IF NOT EXISTS idx_tickets_estado        ON b2b_crm.tickets_soporte(estado);
CREATE INDEX IF NOT EXISTS idx_tickets_prioridad     ON b2b_crm.tickets_soporte(prioridad);
CREATE INDEX IF NOT EXISTS idx_facturacion_estado    ON b2b_crm.facturacion(estado_pago);
CREATE INDEX IF NOT EXISTS idx_mediciones_ts         ON telecomunicaciones.mediciones_performance(enlace_id, timestamp_med DESC);
CREATE INDEX IF NOT EXISTS idx_incidentes_estado     ON telecomunicaciones.incidentes(estado, severidad);
CREATE INDEX IF NOT EXISTS idx_equipos_estado        ON telecomunicaciones.equipos_red(estado);

-- =============================================================================
-- VISTAS para el módulo de Health Check
-- =============================================================================

-- Vista: resumen de conectividad de clientes
CREATE OR REPLACE VIEW b2b_crm.v_resumen_clientes AS
SELECT
    c.id,
    c.razon_social,
    c.segmento,
    c.estado,
    COUNT(DISTINCT ct.id)            AS total_contratos,
    COUNT(DISTINCT ct.id) FILTER (WHERE ct.estado = 'VIGENTE') AS contratos_vigentes,
    SUM(ct.monto_mensual_usd) FILTER (WHERE ct.estado = 'VIGENTE') AS mrr_usd,
    COUNT(DISTINCT ts.id) FILTER (WHERE ts.estado = 'ABIERTO' AND ts.prioridad IN ('P1','P2')) AS tickets_criticos_abiertos
FROM b2b_crm.clientes c
LEFT JOIN b2b_crm.contratos ct ON ct.cliente_id = c.id
LEFT JOIN b2b_crm.tickets_soporte ts ON ts.cliente_id = c.id
GROUP BY c.id, c.razon_social, c.segmento, c.estado;

-- Vista: performance promedio por enlace en las últimas 24h
CREATE OR REPLACE VIEW telecomunicaciones.v_performance_24h AS
SELECT
    e.id                             AS enlace_id,
    e.codigo_enlace,
    e.tipo_enlace,
    e.capacidad_mbps,
    e.estado                         AS estado_enlace,
    COUNT(m.id)                      AS total_mediciones,
    ROUND(AVG(m.latencia_ms), 2)     AS latencia_avg_ms,
    ROUND(MAX(m.latencia_ms), 2)     AS latencia_max_ms,
    ROUND(AVG(m.jitter_ms), 2)       AS jitter_avg_ms,
    ROUND(AVG(m.perdida_pct), 3)     AS perdida_avg_pct,
    ROUND(AVG(m.utilizacion_pct), 1) AS utilizacion_avg_pct,
    ROUND(MAX(m.utilizacion_pct), 1) AS utilizacion_max_pct,
    ROUND(AVG(m.mos_score), 2)       AS mos_avg
FROM telecomunicaciones.enlaces e
LEFT JOIN telecomunicaciones.mediciones_performance m
    ON m.enlace_id = e.id
    AND m.timestamp_med >= NOW() - INTERVAL '24 hours'
GROUP BY e.id, e.codigo_enlace, e.tipo_enlace, e.capacidad_mbps, e.estado;

-- =============================================================================
-- RESUMEN FINAL - Conteo de registros por tabla
-- =============================================================================
DO $$
DECLARE
    v_clientes      INTEGER;
    v_contratos     INTEGER;
    v_servicios     INTEGER;
    v_tickets       INTEGER;
    v_facturas      INTEGER;
    v_equipos       INTEGER;
    v_enlaces       INTEGER;
    v_mediciones    INTEGER;
    v_incidentes    INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_clientes   FROM b2b_crm.clientes;
    SELECT COUNT(*) INTO v_contratos  FROM b2b_crm.contratos;
    SELECT COUNT(*) INTO v_servicios  FROM b2b_crm.servicios_contratados;
    SELECT COUNT(*) INTO v_tickets    FROM b2b_crm.tickets_soporte;
    SELECT COUNT(*) INTO v_facturas   FROM b2b_crm.facturacion;
    SELECT COUNT(*) INTO v_equipos    FROM telecomunicaciones.equipos_red;
    SELECT COUNT(*) INTO v_enlaces    FROM telecomunicaciones.enlaces;
    SELECT COUNT(*) INTO v_mediciones FROM telecomunicaciones.mediciones_performance;
    SELECT COUNT(*) INTO v_incidentes FROM telecomunicaciones.incidentes;

    RAISE NOTICE '============================================================';
    RAISE NOTICE 'CloudDB Sentinel - Setup Demo Data - Resumen de carga';
    RAISE NOTICE '============================================================';
    RAISE NOTICE 'Schema b2b_crm:';
    RAISE NOTICE '  clientes              : % registros', v_clientes;
    RAISE NOTICE '  contratos             : % registros', v_contratos;
    RAISE NOTICE '  servicios_contratados : % registros', v_servicios;
    RAISE NOTICE '  tickets_soporte       : % registros', v_tickets;
    RAISE NOTICE '  facturacion           : % registros', v_facturas;
    RAISE NOTICE 'Schema telecomunicaciones:';
    RAISE NOTICE '  equipos_red           : % registros', v_equipos;
    RAISE NOTICE '  enlaces               : % registros', v_enlaces;
    RAISE NOTICE '  mediciones_performance: % registros', v_mediciones;
    RAISE NOTICE '  incidentes            : % registros', v_incidentes;
    RAISE NOTICE '------------------------------------------------------------';
    RAISE NOTICE '  TOTAL                 : % registros', v_clientes + v_contratos + v_servicios + v_tickets + v_facturas + v_equipos + v_enlaces + v_mediciones + v_incidentes;
    RAISE NOTICE '============================================================';
END $$;
