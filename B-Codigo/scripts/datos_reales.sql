-- Datos reales de eGraduados.
-- Generado por scripts/preparar_carga.py a partir de Datos.sql.
-- Revisar antes de ejecutar. TODO: se carga con
-- `python manage.py cargar_datos_reales`.

INSERT INTO ESCUELA (`id_escuela`, `nombre_escuela`) VALUES
(1, 'Escuela de Ingeniería y Prevención de Riesgos'),
(2, 'Escuela de Sistemas e Informática'),
(3, 'Escuela de Administración y Economía'),
(4, 'Escuela de Ciencias Básicas y Exactas'),
(5, 'Escuela de Comunicación'),
(6, 'Escuela de Enfermería'),
(7, 'Escuela de Geografía, Ordenamiento Territorial y Geoinformación'),
(8, 'Escuela de Historia'),
(9, 'Escuela de Letras'),
(10, 'Escuela de Psicopedagogía'),
(11, 'Escuela de Recursos Naturales'),
(12, 'Escuela de Trabajo Social'),
(13, 'Escuela de Turismo');

INSERT INTO CARRERA (`codigo_carrera`, `nombre_carrera`, `id_escuela`) VALUES
('001', 'Profesorado en Letras', 9),
('003', 'Profesorado en Historia', 8),
('004', 'Profesorado en Geografía', 7),
('016', 'Analista de Sistemas', 2),
('023', 'Ingeniería en Recursos Naturales', 11),
('045', 'Licenciatura en Psicopedagogía', 10),
('046', 'Enfermero Universitario', 6),
('047', 'Licenciatura en Enfermería', 6),
('049', 'Profesorado de Matemática', 4),
('060', 'Licenciatura en Letras', 9),
('061', 'Licenciatura en Turismo', 13),
('062', 'Tecnicatura Universitaria en Turismo', 13),
('064', 'Licenciatura en Geografía', 7),
('069', 'Ingeniería Química', 1),
('072', 'Licenciatura en Sistemas', 2),
('074', 'Licenciatura en Trabajo Social', 12),
('076', 'Tecnicatura Universitaria en Acompañamiento Terapéutico', 6),
('083', 'Ciclo Complementario en Geografía', 7),
('085', 'Ciclo Complementario en Turismo', 13),
('092', 'Licenciatura en Gestión y Administración de Universidades', 3),
('093', 'Licenciatura en Enfermería', 6),
('096', 'Licenciatura en Historia', 8),
('912', 'Tecn. Univ. en Gestión de Organizaciones', 3),
('913', 'Licenciatura en Administración', 3),
('914', 'Profesorado en Economía y Gestión de Organizaciones', 3),
('915', 'Tecn. Univ. en Agronegocios y Recursos Naturales', 11),
('918', 'Licenciatura en Comunicación Social', 5);
