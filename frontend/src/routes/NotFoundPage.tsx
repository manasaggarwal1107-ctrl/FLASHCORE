import { Link } from 'react-router-dom';
import { EmptyState } from '@/components/ui/States';
import { Button } from '@/components/ui/Button';

export function NotFoundPage() {
  return (
    <EmptyState
      title="Page not found"
      description="The address doesn't match any FLASHCORE view."
      action={
        <Link to="/overview">
          <Button variant="primary">Go to Overview</Button>
        </Link>
      }
    />
  );
}
