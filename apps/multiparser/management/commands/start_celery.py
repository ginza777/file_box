import subprocess
import sys
import os
from django.core.management.base import BaseCommand
from django.conf import settings

class Command(BaseCommand):
    help = 'Start Celery worker and beat scheduler'

    def add_arguments(self, parser):
        parser.add_argument(
            '--worker-only',
            action='store_true',
            help='Start only Celery worker (not beat)'
        )
        parser.add_argument(
            '--beat-only',
            action='store_true',
            help='Start only Celery beat (not worker)'
        )
        parser.add_argument(
            '--workers',
            type=int,
            default=10,
            help='Number of worker processes (default: 10)'
        )

    def handle(self, *args, **options):
        worker_only = options['worker_only']
        beat_only = options['beat_only']
        workers = options['workers']

        # Ensure environment is propagated to subprocesses
        env = os.environ.copy()
        if 'DJANGO_SETTINGS_MODULE' not in env:
            # settings.SETTINGS_MODULE is defined by Django when configured
            env['DJANGO_SETTINGS_MODULE'] = getattr(settings, 'SETTINGS_MODULE', 'core.settings.develop')

        # Decide Celery app name (project-level celery app is typically "core")
        celery_app = 'core'

        if not worker_only and not beat_only:
            # Start both worker and beat
            self.stdout.write(
                self.style.SUCCESS('Starting Celery worker and beat scheduler...')
            )

            # Build beat command (conditionally add django_celery_beat scheduler)
            beat_cmd = [
                sys.executable, '-m', 'celery', '-A', celery_app, 'beat',
                '--loglevel=info'
            ]
            if 'django_celery_beat' in getattr(settings, 'INSTALLED_APPS', []):
                beat_cmd.extend(['--scheduler', 'django_celery_beat.schedulers:DatabaseScheduler'])

            beat_process = subprocess.Popen(
                beat_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env
            )

            self.stdout.write(
                self.style.SUCCESS(f'Beat scheduler started with PID: {beat_process.pid}')
            )

            # Start worker
            worker_cmd = [
                sys.executable, '-m', 'celery', '-A', celery_app, 'worker',
                '--loglevel=info', f'--concurrency={workers}'
            ]

            self.stdout.write(
                self.style.SUCCESS(f'Starting worker with {workers} processes...')
            )

            try:
                subprocess.run(worker_cmd, check=True, env=env)
            except KeyboardInterrupt:
                self.stdout.write(
                    self.style.WARNING('\nStopping Celery processes...')
                )
                beat_process.terminate()
                beat_process.wait()
                self.stdout.write(
                    self.style.SUCCESS('Celery processes stopped.')
                )
            except subprocess.CalledProcessError as e:
                self.stderr.write(self.style.ERROR(f'Celery worker failed (exit {e.returncode}).'))
                # Also terminate beat if worker fails to start
                beat_process.terminate()
                beat_process.wait()
                raise

        elif worker_only:
            # Start only worker
            self.stdout.write(
                self.style.SUCCESS(f'Starting Celery worker with {workers} processes...')
            )

            worker_cmd = [
                sys.executable, '-m', 'celery', '-A', celery_app, 'worker',
                '--loglevel=info', f'--concurrency={workers}'
            ]

            try:
                subprocess.run(worker_cmd, check=True, env=env)
            except KeyboardInterrupt:
                self.stdout.write(
                    self.style.SUCCESS('\nWorker stopped.')
                )
            except subprocess.CalledProcessError as e:
                self.stderr.write(self.style.ERROR(f'Celery worker failed (exit {e.returncode}).'))
                raise

        elif beat_only:
            # Start only beat
            self.stdout.write(
                self.style.SUCCESS('Starting Celery beat scheduler...')
            )

            beat_cmd = [
                sys.executable, '-m', 'celery', '-A', celery_app, 'beat',
                '--loglevel=info'
            ]
            if 'django_celery_beat' in getattr(settings, 'INSTALLED_APPS', []):
                beat_cmd.extend(['--scheduler', 'django_celery_beat.schedulers:DatabaseScheduler'])

            try:
                subprocess.run(beat_cmd, check=True, env=env)
            except KeyboardInterrupt:
                self.stdout.write(
                    self.style.SUCCESS('\nBeat scheduler stopped.')
                )
            except subprocess.CalledProcessError as e:
                self.stderr.write(self.style.ERROR(f'Celery beat failed (exit {e.returncode}).'))
                raise
