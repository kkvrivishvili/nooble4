import { MailCheck } from 'lucide-react';

export default function VerifyEmailPage() {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-background text-foreground">
      <div className="max-w-md text-center p-8">
        <div className="flex justify-center mb-6">
          <MailCheck className="w-16 h-16 text-primary" />
        </div>
        <h1 className="text-3xl font-bold mb-2">Verifica tu correo electrónico</h1>
        <p className="text-muted-foreground mb-6">
          Hemos enviado un enlace de verificación a tu dirección de correo. Por favor, haz clic en el enlace para completar tu registro.
        </p>
        <p className="text-sm text-muted-foreground">
          ¿No recibiste el correo? Revisa tu carpeta de spam.
        </p>
      </div>
    </div>
  );
}
