# Análisis del Frontend para la Base de Datos Supabase

Este documento detalla los hallazgos del análisis del frontend para definir la estructura de la base de datos `init.sql`.

## 1. Análisis Inicial (Estructura de `src/app`)

La estructura de directorios inicial sugiere las siguientes características principales:

*   **Autenticación de Usuarios:** La presencia de una carpeta `/auth` indica un sistema de inicio de sesión y registro. 
    *   **Requisito DB:** Necesitaremos una tabla `profiles` para almacenar datos de usuario adicionales, vinculada a la tabla `auth.users` de Supabase.

*   **Sistema Multitenant y de Invitaciones:** La carpeta `/invite` sugiere que los usuarios pueden ser invitados a unirse a un "espacio" o "equipo". Esto es un fuerte indicador de una arquitectura multitenant.
    *   **Requisito DB:** 
        *   Una tabla `organizations` o `workspaces` para definir los inquilinos.
        *   Una tabla `members` para vincular usuarios a organizaciones con roles específicos.
        *   Una tabla `invites` para gestionar las invitaciones pendientes.

*   **Panel de Control (`/dashboard`):** Es el núcleo de la aplicación para usuarios autenticados. El análisis de su contenido revelará las entidades de negocio principales.

## 2. Análisis del Dashboard (`src/app/dashboard`)

La estructura del dashboard confirma y expande nuestro entendimiento:

*   **Organizaciones (`/orgs`):** Confirma definitivamente la arquitectura **multitenant**. La lógica principal de la aplicación reside aquí.
*   **Administración (`/admin`):** Sugiere la existencia de roles de usuario (ej. `admin`, `member`).
    *   **Requisito DB:** La tabla `members` debería incluir una columna `role`.
*   **Perfil y Configuración (`/profile`, `/settings`):** Páginas estándar para la gestión de la cuenta de usuario.

## 3. Análisis de la Organización (`src/app/dashboard/orgs/[slug]`)

Dentro de cada organización, encontramos las siguientes funcionalidades administrativas:

*   **Gestión de Miembros (`/members`):** Una interfaz para ver y gestionar los miembros de la organización.
*   **Gestión de Invitaciones (`/invite`):** Un formulario para invitar a nuevos usuarios a la organización actual.
*   **Configuración de la Organización (`/settings`):** Ajustes específicos para la organización.

El siguiente paso es analizar el contenido de la página principal de la organización (`page.tsx`) y su configuración para descubrir las entidades de negocio (proyectos, chats, documentos, etc.).

## 4. Análisis del Código (`page.tsx` de la Organización)

El análisis del archivo `.../orgs/[slug]/page.tsx` revela la interacción directa con la base de datos y confirma la estructura:

*   **Consulta a Supabase:** El componente realiza una consulta a la base de datos en el servidor para obtener los detalles de la organización.
*   **Tablas Identificadas:**
    *   `organizations`: La tabla principal para los inquilinos. Se accede a las columnas `slug`, `name`, y `created_at`.
    *   `organization_members`: Una tabla que vincula usuarios a organizaciones. Se accede a la columna `role`.
*   **Relaciones:** Existe una relación clara de uno a muchos entre `organizations` y `organization_members`.

*   **¡Descubrimiento Clave! - Tipos de la Base de Datos:** La importación `import type { Database } from '@/types/supabase'` indica que existe un archivo con los tipos de TypeScript autogenerados por Supabase. Este archivo es la **fuente de verdad** para el esquema de base de datos que el frontend espera. El siguiente paso es analizarlo.

## 5. Análisis Final (Archivo `src/types/supabase.ts`)

El archivo `supabase.ts` contiene el esquema completo que el frontend espera. A continuación se detallan las entidades finales:

*   **Enums (Tipos Personalizados):**
    *   `user_role`: ('user', 'admin', 'super_admin') para la tabla `roles`.
    *   Roles de Organización: ('owner', 'admin', 'member') para las tablas `organization_members` y `organization_invites`.

*   **Tablas Principales:**
    *   `profiles`: `id`, `user_id` (FK a `auth.users`), `full_name`, `avatar_url`.
    *   `organizations`: `id`, `name`, `slug` (único), `avatar_url`.
    *   `organization_members`: `org_id` (FK a `organizations`), `user_id` (FK a `auth.users`), `role` (enum), `joined_at`. Clave primaria compuesta por (`org_id`, `user_id`).
    *   `organization_invites`: `id`, `org_id` (FK a `organizations`), `email`, `role` (enum), `invited_by` (FK a `auth.users`), `token` (único), `expires_at`.

*   **Tablas de Soporte y Auditoría:**
    *   `roles`: `id`, `user_id` (FK a `auth.users`), `role` (enum `user_role`).
    *   `user_activity`: `id`, `user_id` (FK a `auth.users`), `action_type`, `metadata` (JSON), `ip_address`, `user_agent`.
    *   `rate_limits`: `id`, `user_id` (FK a `auth.users`), `action_type`, `window_start`, `request_count`.
    *   `organization_member_stats_cache`: `org_id` (FK a `organizations`), `stats` (JSON), `last_updated`.

*   **Funciones de PostgreSQL:**
    *   `check_rate_limit(...)`: Verifica si un usuario ha excedido un límite de acciones.
    *   `get_basic_metrics()`: Devuelve métricas básicas de usuarios.
    *   `get_detailed_analytics()`: Devuelve analíticas detalladas de actividad.
    *   `get_org_member_stats(...)`: Devuelve estadísticas de miembros para una organización.

*   **Almacenamiento (Storage):**
    *   Un bucket llamado `Avatars` para almacenar las imágenes de perfil y de organización. Debe ser público.

Con esta información, se puede construir un archivo `init.sql` completo y preciso.

## 5. Análisis Final (Archivo `src/types/supabase.ts`)

El archivo `supabase.ts` contiene el esquema completo que el frontend espera. A continuación se detallan las entidades finales:

*   **Enums (Tipos Personalizados):**
    *   `user_role`: ('user', 'admin', 'super_admin') para la tabla `roles`.
    *   Roles de Organización: ('owner', 'admin', 'member') para las tablas `organization_members` y `organization_invites`.

*   **Tablas Principales:**
    *   `profiles`: `id`, `user_id` (FK a `auth.users`), `full_name`, `avatar_url`.
    *   `organizations`: `id`, `name`, `slug` (único), `avatar_url`.
    *   `organization_members`: `org_id` (FK a `organizations`), `user_id` (FK a `auth.users`), `role` (enum), `joined_at`. Clave primaria compuesta por (`org_id`, `user_id`).
    *   `organization_invites`: `id`, `org_id` (FK a `organizations`), `email`, `role` (enum), `invited_by` (FK a `auth.users`), `token` (único), `expires_at`.

*   **Tablas de Soporte y Auditoría:**
    *   `roles`: `id`, `user_id` (FK a `auth.users`), `role` (enum `user_role`).
    *   `user_activity`: `id`, `user_id` (FK a `auth.users`), `action_type`, `metadata` (JSON), `ip_address`, `user_agent`.
    *   `rate_limits`: `id`, `user_id` (FK a `auth.users`), `action_type`, `window_start`, `request_count`.
    *   `organization_member_stats_cache`: `org_id` (FK a `organizations`), `stats` (JSON), `last_updated`.

*   **Funciones de PostgreSQL:**
    *   `check_rate_limit(...)`: Verifica si un usuario ha excedido un límite de acciones.
    *   `get_basic_metrics()`: Devuelve métricas básicas de usuarios.
    *   `get_detailed_analytics()`: Devuelve analíticas detalladas de actividad.
    *   `get_org_member_stats(...)`: Devuelve estadísticas de miembros para una organización.

*   **Almacenamiento (Storage):**
    *   Un bucket llamado `Avatars` para almacenar las imágenes de perfil y de organización. Debe ser público.

Con esta información, se puede construir un archivo `init.sql` completo y preciso.
