// Re-seed cua-gym Postgres from the gym projection (312 tasks × 5 apps).
// Manual trigger after seed_to_cuagym / ambient changes. Does NOT deploy UI.
pipeline {
    agent { label 'backend-agent' }

    parameters {
        string(name: 'BRANCH_NAME', defaultValue: 'seed-to-cua-gym', description: 'Gym repo branch')
        booleanParam(name: 'DRY_RUN', defaultValue: false, description: 'Print SQL only, do not execute')
    }

    stages {
        stage('Checkout') {
            steps {
                git(
                    url: 'https://bitbucket.org/deccan-ai/ecommerce-browser-gym.git',
                    branch: params.BRANCH_NAME,
                    credentialsId: 'jenkins_user_bitbucket'
                )
            }
        }

        stage('Seed cua-gym') {
            steps {
                withCredentials([string(credentialsId: 'cua-gym-pg', variable: 'PGPASSWORD')]) {
                    sh '''
                        set -euo pipefail
                        python3 -m venv .venv-seed
                        .venv-seed/bin/pip install -q -e .
                        if [ "${DRY_RUN}" = "true" ]; then
                          .venv-seed/bin/python -m tools.seed_via_psql --dry-run
                        else
                          .venv-seed/bin/python -m tools.seed_via_psql
                        fi
                    '''
                }
            }
        }
    }
}
