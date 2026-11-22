-- Respaldo previo a la carga del Excel de planes de estudio.
SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS `CARRERA`;
CREATE TABLE `carrera` (
  `codigo_carrera` varchar(50) NOT NULL,
  `nombre_carrera` varchar(150) NOT NULL,
  `id_escuela` int NOT NULL,
  `plan_vigente` varchar(50) DEFAULT NULL,
  PRIMARY KEY (`codigo_carrera`),
  UNIQUE KEY `plan_vigente` (`plan_vigente`),
  KEY `CARRERA_id_escuela_0877f239_fk_ESCUELA_id_escuela` (`id_escuela`),
  CONSTRAINT `CARRERA_id_escuela_0877f239_fk_ESCUELA_id_escuela` FOREIGN KEY (`id_escuela`) REFERENCES `escuela` (`id_escuela`),
  CONSTRAINT `CARRERA_plan_vigente_5b576ac6_fk_PLAN_ESTUDIOS_codigo_plan` FOREIGN KEY (`plan_vigente`) REFERENCES `plan_estudios` (`codigo_plan`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

INSERT INTO `CARRERA` (`codigo_carrera`, `nombre_carrera`, `id_escuela`, `plan_vigente`) VALUES
('001', 'Profesorado en Letras', 9, '001-2006'),
('003', 'Profesorado en Historia', 8, '003-2000'),
('004', 'Profesorado en Geografía', 7, '004-2006'),
('016', 'Analista de Sistemas', 2, '016-2023'),
('023', 'Ingeniería en Recursos Naturales', 11, '023-2008'),
('045', 'Licenciatura en Psicopedagogía', 10, '045-2006'),
('046', 'Enfermero Universitario', 6, NULL),
('047', 'Licenciatura en Enfermería', 6, NULL),
('049', 'Profesorado de Matemática', 4, '049-2006'),
('060', 'Licenciatura en Letras', 9, '060-2006'),
('061', 'Licenciatura en Turismo', 13, '061-2005'),
('062', 'Tecnicatura Universitaria en Turismo', 13, '062-2005'),
('064', 'Licenciatura en Geografía', 7, '064-2006'),
('069', 'Ingeniería Química', 1, '069-2023'),
('072', 'Licenciatura en Sistemas', 2, '072-2023'),
('074', 'Licenciatura en Trabajo Social', 12, '074-2007'),
('076', 'Tecnicatura Universitaria en Acompañamiento Terapéutico', 6, '076-2008'),
('083', 'Ciclo Complementario en Geografía', 7, '083-1999'),
('085', 'Ciclo Complementario en Turismo', 13, '085-2010'),
('092', 'Licenciatura en Gestión y Administración de Universidades', 3, NULL),
('093', 'Licenciatura en Enfermería', 6, '093-2017'),
('096', 'Licenciatura en Historia', 8, NULL),
('912', 'Tecn. Univ. en Gestión de Organizaciones', 3, '912-2001'),
('913', 'Licenciatura en Administración', 3, '913-2001'),
('914', 'Profesorado en Economía y Gestión de Organizaciones', 3, '914-2001'),
('915', 'Tecn. Univ. en Agronegocios y Recursos Naturales', 11, '915-2023'),
('918', 'Licenciatura en Comunicación Social', 5, '918-2005');

DROP TABLE IF EXISTS `MATERIA`;
CREATE TABLE `materia` (
  `codigo_materia` varchar(50) NOT NULL,
  `nombre_materia` varchar(150) NOT NULL,
  PRIMARY KEY (`codigo_materia`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

INSERT INTO `MATERIA` (`codigo_materia`, `nombre_materia`) VALUES
('1107', 'Introducción al Conocimiento Científico'),
('1108', 'Ciencia, Universidad y Sociedad'),
('1221', 'Estadística'),
('1345', 'Inteligencia Artificial'),
('1528', 'Álgebra'),
('1530', 'Análisis Matemático I'),
('1531', 'Análisis Matemático II'),
('1649', 'Resolución de Problemas y Algoritmos'),
('1650', 'Matemática Discreta'),
('1652', 'Programación Orientada a Objetos'),
('1654', 'Requerimientos de Software'),
('1656', 'Estructuras de Datos'),
('1658', 'Análisis y Diseño de Software'),
('1659', 'Bases de Datos'),
('1660', 'Laboratorio de Programación'),
('1661', 'Redes y Telecomunicaciones'),
('1662', 'Fundamentos de Ciencias de la Computación'),
('1663', 'Validación y Verificación de Software'),
('1664', 'Gestión de Organizaciones'),
('1665', 'Estadística I'),
('1670', 'Programación Lógica y Funcional'),
('1671', 'Laboratorio de Redes'),
('1672', 'Bases de Datos Distribuidas'),
('1673', 'Gestión de Calidad'),
('1674', 'Estadística II'),
('1676', 'Sistemas de Información'),
('1677', 'Taller de Metodología de la Investigación'),
('1679', 'Seminario de Programación'),
('1681', 'Seminario de Sistemas'),
('1684', 'Procesos de Desarrollo de Software'),
('1987', 'Organización de las Computadoras'),
('1989', 'Aspectos Profesionales'),
('2137', 'Arquitecturas de Computadoras'),
('2138', 'Laboratorio de Desarrollo de Software'),
('2648', 'Resolución de Problemas y Algoritmos'),
('2649', 'Aspectos Profesionales'),
('2651', 'Programación de Algoritmos'),
('2652', 'Procesos de Desarrollo de Software'),
('2654', 'Requerimientos de Software'),
('2657', 'Gestión de Proyectos de Software'),
('2659', 'Sistemas Distribuidos'),
('2706', 'Análisis y Diseño de Software'),
('2707', 'Sistemas Operativos'),
('2708', 'Matemática III'),
('2710', 'Seminario de Computación Móvil'),
('2741', 'Paradigmas de Lenguajes de Programación'),
('387', 'Matemática I'),
('390', 'Matemática II'),
('453', 'Idioma Moderno (Inglés)'),
('901', 'Análisis y Producción del Discurso');

DROP TABLE IF EXISTS `PLAN_ESTUDIOS`;
CREATE TABLE `plan_estudios` (
  `codigo_plan` varchar(50) NOT NULL,
  `codigo_carrera` varchar(50) NOT NULL,
  PRIMARY KEY (`codigo_plan`),
  KEY `PLAN_ESTUDIOS_codigo_carrera_cd431237_fk_CARRERA_codigo_carrera` (`codigo_carrera`),
  CONSTRAINT `PLAN_ESTUDIOS_codigo_carrera_cd431237_fk_CARRERA_codigo_carrera` FOREIGN KEY (`codigo_carrera`) REFERENCES `carrera` (`codigo_carrera`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

INSERT INTO `PLAN_ESTUDIOS` (`codigo_plan`, `codigo_carrera`) VALUES
('001-2006', '001'),
('003-2000', '003'),
('004-2006', '004'),
('016-2007', '016'),
('016-2012', '016'),
('016-2023', '016'),
('023-1995', '023'),
('023-2001', '023'),
('023-2008', '023'),
('045-1999', '045'),
('045-2006', '045'),
('049-2006', '049'),
('060-2000', '060'),
('060-2006', '060'),
('061-2005', '061'),
('062-2005', '062'),
('064-2006', '064'),
('069-2007', '069'),
('069-2008', '069'),
('069-2023', '069'),
('072-1999', '072'),
('072-2012', '072'),
('072-2023', '072'),
('074-2007', '074'),
('076-2008', '076'),
('083-1999', '083'),
('085-2010', '085'),
('093-1998', '093'),
('093-2017', '093'),
('912-2001', '912'),
('913-2001', '913'),
('913-2001-HOM', '913'),
('914-2001', '914'),
('915-2001', '915'),
('915-2023', '915'),
('918-2005', '918');

DROP TABLE IF EXISTS `DETALLE_PLAN_ESTUDIOS`;
CREATE TABLE `detalle_plan_estudios` (
  `codigo_plan` varchar(50) NOT NULL,
  `anio` int DEFAULT NULL,
  `tipo` varchar(20) NOT NULL,
  `archivo` varchar(100) DEFAULT NULL,
  `nombre_original` varchar(255) NOT NULL,
  `hash_archivo` varchar(64) NOT NULL,
  `resolucion` varchar(100) NOT NULL,
  `observaciones` longtext NOT NULL,
  PRIMARY KEY (`codigo_plan`),
  KEY `DETALLE_PLAN_ESTUDIOS_hash_archivo_39ed9a01` (`hash_archivo`),
  CONSTRAINT `DETALLE_PLAN_ESTUDIO_codigo_plan_17bb81eb_fk_PLAN_ESTU` FOREIGN KEY (`codigo_plan`) REFERENCES `plan_estudios` (`codigo_plan`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

INSERT INTO `DETALLE_PLAN_ESTUDIOS` (`codigo_plan`, `anio`, `tipo`, `archivo`, `nombre_original`, `hash_archivo`, `resolucion`, `observaciones`) VALUES
('001-2006', 2006, 'VIGENTE', 'planes_estudio/a0c96aa44d_001 - Profesorado en Letras_2006.pdf', '001 - Profesorado en Letras_2006.pdf', 'a0c96aa44d3311494069406129257629ffcd6e038fbd9aeace3ea49b7e316d38', '', ''),
('003-2000', 2000, 'VIGENTE', 'planes_estudio/04aec0be46_003 - Profesorado en Historia_2000.pdf', '003 - Profesorado en Historia_2000.pdf', '04aec0be46ffc7d6150168559c42876f5410bbcd1b4e83b6e5215b7a4d748068', '', ''),
('004-2006', 2006, 'VIGENTE', 'planes_estudio/f35d3b197b_004 - Profesorado en Geografía_2006.pdf', '004 - Profesorado en Geografía_2006.pdf', 'f35d3b197bf428260feae912779f3736aadbd404dc0359254c0c35f4089baf36', '', ''),
('016-2007', 2007, 'HISTORICO', 'planes_estudio/74335f014c_Analista de Sistemas (016).pdf', 'Analista de Sistemas (016).pdf', '74335f014c066cd9c751f7389d43420f805f1058c33f3ec6c5c262e03e8107d4', '', 'Año estimado del PDF (2007); revisar'),
('016-2012', 2012, 'HISTORICO', 'planes_estudio/de79d35dff_016 - Analista de Sistema_2012.pdf', '016 - Analista de Sistema_2012.pdf', 'de79d35dff40b6f6c89dd127c8dbcb3556177a206cacfffcfc90bb61c1c0edd2', '', ''),
('016-2023', 2023, 'VIGENTE', 'planes_estudio/71062dc9ee_016 - Analista de Sistemas_2023.pdf', '016 - Analista de Sistemas_2023.pdf', '71062dc9eee30d8986ca851402a7ed1a39923d2c9fddc6bfa5b35b06abea6d72', '', ''),
('023-1995', 1995, 'HISTORICO', 'planes_estudio/594352f30d_023 - IRNR_1995.pdf', '023 - IRNR_1995.pdf', '594352f30da969b9cf7e36275ed28e9fae5a7ba245443f0fe3247a28dbb5b842', '', ''),
('023-2001', 2001, 'HISTORICO', 'planes_estudio/f22f9718e6_023 - IRNR_2001.pdf', '023 - IRNR_2001.pdf', 'f22f9718e6527ebcb2b05bc1fc8e789d7a02671131f1bb3f565132f76a68892b', '', ''),
('023-2008', 2008, 'VIGENTE', 'planes_estudio/1bd2c16056_023 - IRNR_2008.pdf', '023 - IRNR_2008.pdf', '1bd2c1605638a10b27c3e5884e412801b23385dd9a231d3aef9f3e3ac1baf9cd', '', ''),
('045-1999', 1999, 'HISTORICO', 'planes_estudio/0e8a32278f_Licenciatura en psicopedagogia (Plan Viejo).pdf', 'Licenciatura en psicopedagogia (Plan Viejo).pdf', '0e8a32278fd5c58bb6aa5792d45d0d534d0c619faf1571cf1012c3fbc662ed4c', '', 'Plan viejo, año estimado; revisar'),
('045-2006', 2006, 'VIGENTE', 'planes_estudio/99c87c4843_045 - Licenciatura en Psicopedagogia_2006.pdf', '045 - Licenciatura en Psicopedagogia_2006.pdf', '99c87c48435ea7c850eedd627f25f100ff6cb01df856837c00102dbe652637e8', '', ''),
('049-2006', 2006, 'VIGENTE', 'planes_estudio/7fcb60473c_049 - Profesorado en Matemática_2006.pdf', '049 - Profesorado en Matemática_2006.pdf', '7fcb60473c450dd8819ebca86986d7956a2a40ba855bbd8f0f08dceb5040ba5f', '', ''),
('060-2000', 2000, 'HISTORICO', 'planes_estudio/a6be65c26e_060 - Licenciatura en Letras_2000.pdf', '060 - Licenciatura en Letras_2000.pdf', 'a6be65c26e88ff52a468738bf0d3a2bad11f6aedae3df174c8def8d322137ab3', '', ''),
('060-2006', 2006, 'VIGENTE', 'planes_estudio/ba83d6d8ee_060 - Licenciatura en Letras_2006.pdf', '060 - Licenciatura en Letras_2006.pdf', 'ba83d6d8ee570edb507828823e2a914cd1649d5d3deac49f75e8d51ec927b9cd', '', ''),
('061-2005', 2005, 'VIGENTE', 'planes_estudio/6bc5ebcc69_061 - Licenciatura en Turismo_2005.pdf', '061 - Licenciatura en Turismo_2005.pdf', '6bc5ebcc692039023cc167767b5b29805c8c9fb21da5a3d5f013f2c53fc22df9', '', ''),
('062-2005', 2005, 'VIGENTE', 'planes_estudio/3ba478c1de_062 - Tecnicatura Universitaria en Turismo_2005.pdf', '062 - Tecnicatura Universitaria en Turismo_2005.pdf', '3ba478c1dec5c0b305b82c9234e5d6bb1ea1dacaac1516ee018e0e0b2b02c8b0', '', ''),
('064-2006', 2006, 'VIGENTE', 'planes_estudio/bd65b0a7f7_064 - Licenciatura en Geografía_2006.pdf', '064 - Licenciatura en Geografía_2006.pdf', 'bd65b0a7f74695636216b703bf30c021bf8297e60fb1ea8f97b6ccf104269fdd', '', ''),
('069-2007', 2007, 'HISTORICO', 'planes_estudio/d2e8d0d2f3_069 - Ing en Quimica_2007.pdf', '069 - Ing en Quimica_2007.pdf', 'd2e8d0d2f3178ceb855a71e8113aa0109564a8c115302d68ebb134b6b87260fa', '', ''),
('069-2008', 2008, 'HISTORICO', 'planes_estudio/438df3597c_069 - Ing en Quimica _2008.pdf', '069 - Ing en Quimica _2008.pdf', '438df3597c329d989f30409a21b6fa83ff8958da9f4df3c65b0e75804d729ae6', '', ''),
('069-2023', 2023, 'VIGENTE', 'planes_estudio/02dd4e3711_069 - Ingenieria Quimica_2023.pdf', '069 - Ingenieria Quimica_2023.pdf', '02dd4e37110fc6059479a9856467e9c2da1041c99f3357d8dabb06013b28a99a', '', ''),
('072-1999', 1999, 'HISTORICO', 'planes_estudio/2ba795fdda_Licenciatura en Sistemas (072).pdf', 'Licenciatura en Sistemas (072).pdf', '2ba795fddacf11c7951ad8c5ed3043260324503e18fd1ee0e53ba264db0e5891', '', 'Año estimado del PDF (1999); revisar'),
('072-2012', 2012, 'HISTORICO', 'planes_estudio/681087dadb_072 - Licenciatura en Sistemas_2012.pdf', '072 - Licenciatura en Sistemas_2012.pdf', '681087dadbf4fbea968a4e471409e80f3fa7ad82f990c96a6a4ca082c76da9d6', '', ''),
('072-2023', 2023, 'VIGENTE', 'planes_estudio/809984560b_072 - Lic. en Sistemas_2023.pdf', '072 - Lic. en Sistemas_2023.pdf', '809984560b6a4bd9a4a896de9f4c303e909c9c568fc1187c6dea86245952e836', '', ''),
('074-2007', 2007, 'VIGENTE', 'planes_estudio/da1a3cdd3c_074 - Licenciatura en Trabajo Social_2007.pdf', '074 - Licenciatura en Trabajo Social_2007.pdf', 'da1a3cdd3cc1d8c4eff17311e7267fc641a18779ea75c2bde83380e98ea35009', '', ''),
('076-2008', 2008, 'VIGENTE', 'planes_estudio/28bb28d6db_076 - Tecn. Univ. en Acomp. Terapeutico_2008.pdf', '076 - Tecn. Univ. en Acomp. Terapeutico_2008.pdf', '28bb28d6dbc87f5052480f3dbfccbb39883866e091a5cd48972f7c7b0c6ad6fd', '', ''),
('083-1999', 1999, 'VIGENTE', 'planes_estudio/558af59df5_Licenciatura en Geografía - Ciclo Complementario.pdf', 'Licenciatura en Geografía - Ciclo Complementario.pdf', '558af59df571cba073e81ded210ba890c1333e58f1a89177b8b5de6d25a86cff', '', 'Año estimado; revisar'),
('085-2010', 2010, 'VIGENTE', 'planes_estudio/71ddbb80d2_Licenciatura en Turismo- ciclo complementario119-10 CS UNPA.pdf', 'Licenciatura en Turismo- ciclo complementario119-10 CS UNPA.pdf', '71ddbb80d271e74a40bc33014e31485385969b7a364daf8204d2261aa5b7888c', '119/10-CS-UNPA', ''),
('093-1998', 1998, 'HISTORICO', 'planes_estudio/2bacdb283b_093 - Lic. en Enfermeria y Enfermeria Univ_1998.pdf', '093 - Lic. en Enfermeria y Enfermeria Univ_1998.pdf', '2bacdb283bb2d68ac4bdd87d57e4f30c4150be75e2c2d9d0bf12ac4d1ea41f17', '', 'Incluye Enfermería Universitaria (046)'),
('093-2017', 2017, 'VIGENTE', 'planes_estudio/942ced4c41_093 - Licenciatura en Enfermeria_2017.pdf', '093 - Licenciatura en Enfermeria_2017.pdf', '942ced4c418ca70fc610413e83e43c50edcd7d3a232f3dd6a8e146c5ece3bf88', '', ''),
('912-2001', 2001, 'VIGENTE', 'planes_estudio/ca85505d1b_912 - TUGO-Tecn. Univ. en Gest. de Org_2001.pdf', '912 - TUGO-Tecn. Univ. en Gest. de Org_2001.pdf', 'ca85505d1b702fec9092daa1e72634d685119664570ac84796152ef69b790117', '', ''),
('913-2001', 2001, 'VIGENTE', 'planes_estudio/a840301450_913 - Licenciatura en Administración_2001.pdf', '913 - Licenciatura en Administración_2001.pdf', 'a840301450b0e98f8075751ef11de2012666693eeb06971241fc6b46f867432f', '', 'Vigente: se prefiere la versión sin homologación'),
('913-2001-HOM', 2001, 'HISTORICO', 'planes_estudio/bdfaf2e900_913 - Licenciatura en Administración con homologación_2001.pdf', '913 - Licenciatura en Administración con homologación_2001.pdf', 'bdfaf2e9006cf4835498699bffc8c81ba26e78edb65572d775628d8dfb643f7b', '', 'Versión con homologación'),
('914-2001', 2001, 'VIGENTE', 'planes_estudio/75280e49aa_914 - PREGO-Profesorado en Econ. y Gest. de Organiz_2001.pdf', '914 - PREGO-Profesorado en Econ. y Gest. de Organiz_2001.pdf', '75280e49aaf444a928f219a9f70edcf47c4610d24d469f084f80ce3161ca9176', '', ''),
('915-2001', 2001, 'HISTORICO', 'planes_estudio/6960171707_TUAGRIES (915).pdf', 'TUAGRIES (915).pdf', '6960171707f73ff6ac556b52ce70c3e17d2df42e6cadbf07da97c879f929d60b', '', 'Año estimado del PDF (2001); revisar'),
('915-2023', 2023, 'VIGENTE', 'planes_estudio/1499da3884_069_TECNICATURA EN ANALISIS QUÍMICO_TIT INTERMEDIO_2023.pdf', '069_TECNICATURA EN ANALISIS QUÍMICO_TIT INTERMEDIO_2023.pdf', '1499da38845b27e4cbaa8050215007808dfa693599214f9553ee8d7491697ab4', '', 'Título intermedio de Ingeniería Química'),
('918-2005', 2005, 'VIGENTE', 'planes_estudio/27d87b4aee_918 - Licenciatura en Comunicacion Social_2005.pdf', '918 - Licenciatura en Comunicacion Social_2005.pdf', '27d87b4aee27bc7bf525499ba4839cd4e5f4a26ff511717221bac3992e78fb83', '', '');

DROP TABLE IF EXISTS `PLAN_ESTUDIOS_MATERIA`;
CREATE TABLE `plan_estudios_materia` (
  `anio_materia` int DEFAULT NULL,
  `cuatrimestre_materia` varchar(3) DEFAULT NULL,
  `orden_materia` int DEFAULT NULL,
  `materia_requisito` tinyint(1) NOT NULL,
  `codigo_materia` varchar(50) NOT NULL,
  `codigo_plan` varchar(50) NOT NULL,
  `id_grupo_optativo` int DEFAULT NULL,
  PRIMARY KEY (`codigo_plan`,`codigo_materia`),
  KEY `PLAN_ESTUDIOS_MATERI_codigo_materia_909ed12b_fk_MATERIA_c` (`codigo_materia`),
  KEY `PLAN_ESTUDIOS_MATERI_id_grupo_optativo_79f88fa7_fk_GRUPO_OPT` (`id_grupo_optativo`),
  CONSTRAINT `PLAN_ESTUDIOS_MATERI_codigo_materia_909ed12b_fk_MATERIA_c` FOREIGN KEY (`codigo_materia`) REFERENCES `materia` (`codigo_materia`),
  CONSTRAINT `PLAN_ESTUDIOS_MATERI_codigo_plan_d08d3a5f_fk_PLAN_ESTU` FOREIGN KEY (`codigo_plan`) REFERENCES `plan_estudios` (`codigo_plan`),
  CONSTRAINT `PLAN_ESTUDIOS_MATERI_id_grupo_optativo_79f88fa7_fk_GRUPO_OPT` FOREIGN KEY (`id_grupo_optativo`) REFERENCES `grupo_optativo` (`id_grupo_optativo`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

INSERT INTO `PLAN_ESTUDIOS_MATERIA` (`anio_materia`, `cuatrimestre_materia`, `orden_materia`, `materia_requisito`, `codigo_materia`, `codigo_plan`, `id_grupo_optativo`) VALUES
(1, '1er', 1, 0, '1107', '001-2006', NULL),
(1, 'A', 2, 0, '901', '001-2006', NULL);

DROP TABLE IF EXISTS `GRUPO_OPTATIVO`;
CREATE TABLE `grupo_optativo` (
  `id_grupo_optativo` int NOT NULL AUTO_INCREMENT,
  `nombre_grupo` varchar(150) NOT NULL,
  `codigo_plan` varchar(50) NOT NULL,
  PRIMARY KEY (`id_grupo_optativo`),
  UNIQUE KEY `uniq_grupo_optativo_por_plan` (`codigo_plan`,`nombre_grupo`),
  CONSTRAINT `GRUPO_OPTATIVO_codigo_plan_c088f517_fk_PLAN_ESTUDIOS_codigo_plan` FOREIGN KEY (`codigo_plan`) REFERENCES `plan_estudios` (`codigo_plan`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `PLAN_ESTUDIOS_GRUPO_OPTATIVO`;
CREATE TABLE `plan_estudios_grupo_optativo` (
  `codigo_plan` varchar(50) NOT NULL,
  `id_grupo_optativo` int NOT NULL,
  `anio_materia` int NOT NULL,
  `cuatrimestre_materia` varchar(3) NOT NULL,
  `orden_materia` int NOT NULL,
  PRIMARY KEY (`codigo_plan`,`id_grupo_optativo`),
  KEY `PLAN_ESTUDIOS_GRUPO__id_grupo_optativo_6ae6afb1_fk_GRUPO_OPT` (`id_grupo_optativo`),
  CONSTRAINT `PLAN_ESTUDIOS_GRUPO__codigo_plan_6e59898d_fk_PLAN_ESTU` FOREIGN KEY (`codigo_plan`) REFERENCES `plan_estudios` (`codigo_plan`),
  CONSTRAINT `PLAN_ESTUDIOS_GRUPO__id_grupo_optativo_6ae6afb1_fk_GRUPO_OPT` FOREIGN KEY (`id_grupo_optativo`) REFERENCES `grupo_optativo` (`id_grupo_optativo`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `EXAMEN`;
CREATE TABLE `examen` (
  `id_examen` int NOT NULL AUTO_INCREMENT,
  `acta_respaldatoria` varchar(50) DEFAULT NULL,
  `tipo_examen` varchar(100) NOT NULL,
  `fecha_examen` date DEFAULT NULL,
  `codigo_materia` varchar(50) NOT NULL,
  PRIMARY KEY (`id_examen`),
  UNIQUE KEY `uniq_examen_acta_materia` (`acta_respaldatoria`,`codigo_materia`),
  KEY `EXAMEN_codigo_materia_f87fc20f_fk_MATERIA_codigo_materia` (`codigo_materia`),
  CONSTRAINT `EXAMEN_codigo_materia_f87fc20f_fk_MATERIA_codigo_materia` FOREIGN KEY (`codigo_materia`) REFERENCES `materia` (`codigo_materia`)
) ENGINE=InnoDB AUTO_INCREMENT=68 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

INSERT INTO `EXAMEN` (`id_examen`, `acta_respaldatoria`, `tipo_examen`, `fecha_examen`, `codigo_materia`) VALUES
(50, 'RG07206139', 'Final', '2024-07-08', '2649'),
(51, 'RG07206151', 'Final', '2024-07-11', '2652'),
(52, 'RG07206157', 'Final', '2024-08-06', '387'),
(53, 'RG07206176', 'Final', '2024-08-08', '2648'),
(54, 'RG07207017', 'Final', '2024-12-05', '1987'),
(55, 'RG07207021', 'Final', '2024-12-05', '2651'),
(56, 'RG07207025', 'Final Libre', '2024-12-12', '453'),
(57, 'RG07207045', 'Final', '2024-12-17', '390'),
(58, 'RG07207108', 'Final', '2025-07-08', '1664'),
(59, 'RG07207124', 'Final', '2025-07-10', '2654'),
(60, 'RG07207127', 'Final', '2025-07-11', '2137'),
(61, 'RG07207146', 'Final', '2025-08-01', '1652'),
(62, 'RG07207194', 'Final', '2025-12-09', '2707'),
(63, 'RG07208053', 'Final', '2026-02-12', '2706'),
(64, 'RG07208065', 'Final', '2026-03-04', '1221'),
(65, 'RG07208136', 'Final', '2026-07-06', '1663'),
(66, 'RG07208145', 'Final', '2026-07-07', '2657'),
(67, 'RG07208170', 'Final', '2026-08-04', '1659');

SET FOREIGN_KEY_CHECKS = 1;
