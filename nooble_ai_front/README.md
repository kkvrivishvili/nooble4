<div align="center">
  <img src="https://github.com/Vindusvisker/Boilerpla.te/blob/main/public/images/boiler-plate-readme-background.jpeg?raw=true" alt="SaaS Boilerplate Banner" width="100%" />
</div>


# Modern SaaS Boilerplate

A modular, scalable, and reusable SaaS boilerplate built with Next.js 15, TypeScript, Tailwind CSS, and Supabase.

## Features

- 🔐 **Authentication** - Supabase Auth with OAuth and magic links
- 👥 **Profile System** - Secure avatar uploads and profile management
- 👥 **Role-Based Access Control** - Granular permissions with user roles
- 📊 **Admin Dashboard** - Complete user and role management
- 📝 **Activity Logging** - Track user actions and system events
- 💳 **Payments** - Stripe integration for subscriptions (Coming Soon)
- 🤖 **AI/LLM Integration** - OpenAI and Anthropic APIs (Coming Soon)
- 🎨 **UI Components** - Reusable components with Tailwind CSS
- 📚 **Database** - Supabase (PostgreSQL) with type safety
- 🚀 **Edge-Ready** - Optimized for Vercel deployment

## Authentication Features

- 🔑 Email/Password authentication
- 🌐 OAuth providers (Google, with GitHub coming soon)
- ✉️ Magic link authentication
- 📧 Email verification flow
- 🔄 Password reset functionality
- 💾 Remember me functionality
- 👤 Profile management
- ⚡ Session management
- 🛡️ Protected routes with middleware

## Admin Features

- 👤 **User Management** - View and manage all users
- 🎭 **Role Management** - Assign and modify user roles
- 📋 **Activity Monitoring** - Track user actions and system events
- 🔐 **Permission System** - Granular access control
- 📊 **System Overview** - Monitor system health and usage

## Role-Based Access Control

The boilerplate includes a comprehensive RBAC system with:

- 🎭 **Role Hierarchy**
  - `super_admin` - Full system access
  - `admin` - Administrative access
  - `user` - Standard user access

- 🛡️ **Permission Gates**
  - Component-level access control
  - Route protection based on roles
  - API endpoint authorization

- ⚙️ **Role Management**
  - Dynamic role assignment
  - Role-based UI adaptation
  - Secure role modification

## Environment Setup

1. Copy the example environment file:
```bash
cp .env.example .env.local
```

2. Update `.env.local` with your credentials:

```bash
# Supabase
NEXT_PUBLIC_SUPABASE_URL=your-supabase-url
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-supabase-anon-key

# Authentication (Optional)
NEXT_PUBLIC_AUTH_ALLOWED_EMAILS=comma,separated,emails
NEXT_PUBLIC_AUTH_BLOCKED_EMAILS=comma,separated,emails

# Stripe (Coming Soon)
STRIPE_SECRET_KEY=your-stripe-secret
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=your-stripe-publishable
STRIPE_WEBHOOK_SECRET=your-stripe-webhook-secret

# OpenAI (Coming Soon)
OPENAI_API_KEY=your-openai-key
```

Note: We use `.env.local` for local development. The `.env.example` file serves as a template and should be committed to the repository without sensitive values.

## Database Setup

1. Create a new project in Supabase
2. Run the following SQL commands in the SQL editor:

```sql
-- Create profiles table
create table public.profiles (
  id uuid references auth.users on delete cascade not null primary key,
  updated_at timestamp with time zone,
  full_name text,
  avatar_url text
);

-- Enable RLS
alter table public.profiles enable row level security;

-- Create policies
create policy "Public profiles are viewable by everyone."
  on public.profiles for select
  using ( true );

create policy "Users can insert their own profile."
  on public.profiles for insert
  with check ( auth.uid() = id );

create policy "Users can update own profile."
  on public.profiles for update
  using ( auth.uid() = id );
```

## Roadmap

### Core Features
- [x] Authentication with Supabase
- [x] User profiles
- [x] Session management
- [x] Role-based access control
- [x] Admin dashboard
- [x] User activity tracking
- [x] Analytics foundation
- [x] Data exports (CSV)

### Team Features (In Progress)
- [x] Organization system foundation
  - [x] Create organizations
  - [x] Organization routing (`/orgs/[slug]`)
  - [x] Basic organization context
  - [ ] Organization dashboard
- [ ] Organization Management
  - [x] Role-based organization access
  - [x] Organization creation flow
  - [ ] Organization settings
  - [ ] Avatar management
  - [ ] Slug management
- [ ] Member Management
  - [ ] Invite system
  - [ ] Role assignment
  - [ ] Member removal
  - [ ] Permission management
- [ ] Organization Features
  - [ ] Activity logging
  - [ ] Member analytics
  - [ ] Resource usage tracking
  - [ ] Organization-wide settings

### Payment Integration
- [ ] Stripe subscriptions
- [ ] Usage-based billing
- [ ] Team billing
- [ ] Invoice management
- [ ] Billing dashboard

### AI/LLM Features
- [ ] OpenAI integration
- [ ] Claude/Anthropic setup
- [ ] Prompt management
- [ ] Usage tracking & limits
- [ ] AI playground

### Advanced Features
- [ ] System settings panel
- [ ] i18n support
- [ ] Documentation system
- [ ] Blog/CMS integration
- [ ] Email template system
- [ ] Webhook system
- [ ] Rate limiting

## Prerequisites

- Node.js 18+ 
- pnpm 8+
- Supabase account
- Basic knowledge of TypeScript and React

## Quick Start

1. Clone the repository:
```bash
git clone https://github.com/yourusername/saas-boilerplate.git
cd saas-boilerplate
```

2. Install dependencies:
```bash
pnpm install
```

3. Copy the environment variables:
```bash
cp .env.example .env.local
```

4. Update the environment variables in `.env.local`

5. Start the development server:
```bash
pnpm dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

## Project Structure

```
src/
├── app/                
│   ├── admin/         # Admin dashboard pages
│   │   ├── overview   # System overview
│   │   ├── users      # User management
│   │   └── roles      # Role management
│   ├── auth/          # Authentication pages
│   ├── dashboard/     # Protected dashboard routes
│   └── api/           # API routes
├── components/        
│   ├── admin/         # Admin dashboard components
│   │   ├── UserManagement.tsx
│   │   ├── RoleManager.tsx
│   │   └── ActivityLog.tsx
│   ├── auth/          # Auth components
│   ├── rbac/          # Role-based access components
│   │   ├── RoleGate.tsx
│   │   └── withRole.tsx
│   └── ui/            # Shared UI components
└── lib/              
    ├── auth/          # Auth utilities
    ├── rbac/          # RBAC utilities
    └── db/            # Database utilities
```

## Tech Stack

- **Framework:** [Next.js 14](https://nextjs.org/)
- **Language:** [TypeScript](https://www.typescriptlang.org/)
- **Styling:** [Tailwind CSS](https://tailwindcss.com/)
- **Database:** [Supabase](https://supabase.com/)
- **Authentication:** Supabase Auth
- **UI Components:** [Radix UI](https://www.radix-ui.com/)
- **Icons:** [Lucide Icons](https://lucide.dev/)
- **Toast:** [Sonner](https://sonner.emilkowal.ski/)
- **Form Validation:** [Zod](https://zod.dev/)
- **Utilities:** clsx, tailwind-merge

## Development

- `pnpm dev` - Start development server
- `pnpm build` - Create production build
- `pnpm start` - Start production server
- `pnpm lint` - Run ESLint

## Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Security Features

- 🔒 Route protection with middleware
- 🚫 Role-based access control
- 📝 Activity logging
- 👥 User management controls
- 🔐 Permission-based UI rendering
- 🚫 Email allowlist/blocklist
- 🔄 Automatic session refresh
- 📤 Secure session logout
- 🔐 Multiple device session management

## Component Library

The boilerplate includes several pre-built components:

- `Button` - Customizable button component
- `Input` - Form input with validation
- `Card` - Content container with variants
- `Dialog` - Modal dialog component
- `Form` - Form components with validation
- `Toast` - Notification system
- `Dropdown` - Menu dropdown component
- `Tabs` - Tabbed interface component

## API Routes

- `/api/auth/*` - Authentication endpoints
- `/api/profile/*` - Profile management
- `/api/sessions/*` - Session management

## Folder Structure Details

```
src/
├── app/                
│   ├── admin/         # Admin dashboard pages
│   │   ├── overview   # System overview
│   │   ├── users      # User management
│   │   └── roles      # Role management
│   ├── auth/          # Authentication pages
│   ├── dashboard/     # Protected dashboard routes
│   └── api/           # API routes
├── components/        
│   ├── admin/         # Admin dashboard components
│   │   ├── UserManagement.tsx
│   │   ├── RoleManager.tsx
│   │   └── ActivityLog.tsx
│   ├── auth/          # Auth components
│   ├── rbac/          # Role-based access components
│   │   ├── RoleGate.tsx
│   │   └── withRole.tsx
│   └── ui/            # Shared UI components
└── lib/              
    ├── auth/          # Auth utilities
    ├── rbac/          # RBAC utilities
    └── db/            # Database utilities
```

## Common Issues

### Authentication

1. **Session not persisting:**
   - Check if cookies are being properly set
   - Verify CORS settings in Supabase

2. **OAuth errors:**
   - Ensure redirect URLs are configured correctly
   - Check allowed callback URLs in Supabase

### Development

1. **Type errors:**
   - Run `pnpm generate-types` to update Supabase types
   - Ensure TypeScript version is compatible

2. **Build errors:**
   - Clear `.next` cache: `rm -rf .next`
   - Verify all environment variables are set

## Configuration Files

- `.env.local` - Local environment variables (not committed)
- `.env.example` - Example environment variables template
- `next.config.ts` - Next.js configuration
- `tailwind.config.ts` - Tailwind CSS configuration
- `tsconfig.json` - TypeScript configuration
- `postcss.config.mjs` - PostCSS configuration
- `eslint.config.mjs` - ESLint configuration

## Analytics Features

The boilerplate includes a comprehensive analytics system:

### User Activity Tracking
- 📊 Real-time activity monitoring
- 👥 Unique user engagement metrics
- 📈 Action frequency analysis
- 🕒 Temporal activity patterns

### Key Metrics
- Daily Active Users (DAU)
- Total action counts
- User engagement rates
- Activity type distribution

### Activity Logging
- Detailed action timestamps
- User-specific activity trails
- Action type categorization
- Multi-timeframe analysis

### Export Capabilities
- CSV data export
- JSON format export
- Custom date range selection
- Filtered data exports

### Future Enhancements
- [x] Activity visualizations (charts/graphs)
- [ ] Custom metric definitions
- [ ] Automated reports
- [ ] Advanced filtering options
- [ ] User behavior analysis
- [ ] Conversion tracking
- [ ] Integration with external analytics

## Profile Features

- 🖼️ **Avatar Management**
  - Secure image upload and storage
  - Client-side image cropping
  - Automatic image compression
  - Rate-limited operations
  
- 👤 **Profile Management**
  - Secure profile updates
  - Type-safe interfaces
  - Real-time validation
  - OAuth profile sync

- 🔒 **Security Features**
  - Server-side storage operations
  - CSRF protection
  - Rate limiting
  - Ownership validation
  - Secure file handling

- 🖼️ Secure avatar storage
- 🔒 Rate-limited profile operations
- 🛡️ Type-safe profile interfaces
