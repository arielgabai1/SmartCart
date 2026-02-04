pipeline {
    agent any

    environment {
        ECR_URL    = '043187663485.dkr.ecr.ap-south-1.amazonaws.com/smartcart'
        S3_BUCKET  = 'smartcart-frontend'
        AWS_REGION = 'ap-south-1'
        DOMAIN     = 'smartcart.arielgabai.com'
    }

    options {
        buildDiscarder(logRotator(numToKeepStr: '10'))
        timeout(time: 10, unit: 'MINUTES')
        disableConcurrentBuilds()
        timestamps()
    }

    stages {

        stage('Version Calculation') {
            when { branch 'main' }
            steps {
                withCredentials([usernamePassword(credentialsId: 'GitLab PAT', usernameVariable: 'GIT_USER', passwordVariable: 'GIT_TOKEN')]) {
                    script {
                        sh "git fetch https://\${GIT_USER}:\${GIT_TOKEN}@gitlab.com/arielgabai/smartcart.git --tags"
                        def latestTag = sh(script: 'git tag --sort=-v:refname | head -1', returnStdout: true).trim()
                        def (major, minor, patch) = latestTag.tokenize('.')
                        env.VERSION = "${major}.${minor}.${patch.toInteger() + 1}"
                    }
                }
            }
        }

        stage('Build Backend Image') {
            when { anyOf { branch 'main'; branch 'feature/*' } }
            steps {
                script {
                    env.IMAGE_TAG = env.VERSION ?: 'dev'
                    env.BACKEND_IMAGE = "${ECR_URL}:${env.IMAGE_TAG}"
                    docker.build(env.BACKEND_IMAGE)
                }
            }
        }

        stage('Security Analysis') {
            when { anyOf { branch 'main'; branch 'feature/*' } }
            parallel {
                stage('Bandit') {
                    steps {
                        script {
                            docker.image(env.BACKEND_IMAGE).inside {
                                sh 'bandit -r src/ -f json -o bandit.json -c tests/bandit.yaml --severity-level high'
                            }
                        }
                        archiveArtifacts artifacts: 'bandit.json', allowEmptyArchive: true
                    }
                }
                stage('pip-audit') {
                    steps {
                        script {
                            docker.image(env.BACKEND_IMAGE).inside {
                                sh 'pip-audit --format=json -o pip-audit.json'
                            }
                        }
                        archiveArtifacts artifacts: 'pip-audit.json', allowEmptyArchive: true
                    }
                }
                stage('Trivy') {
                    steps {
                        sh "docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy:latest image --severity CRITICAL --ignore-unfixed --exit-code 1 --format json ${env.BACKEND_IMAGE} > trivy.json"
                        archiveArtifacts artifacts: 'trivy.json', allowEmptyArchive: true
                    }
                }
            }
        }

        stage('Unit Tests') {
            when { anyOf { branch 'main'; branch 'feature/*' } }
            steps {
                script {
                    docker.image(env.BACKEND_IMAGE).inside {
                        sh 'pytest tests/unit_tests.py --cov=src --cov-report=xml:coverage.xml'
                    }
                }
            }
        }

        stage('SonarCloud Analysis') {
            when { anyOf { branch 'main'; branch 'feature/*' } }
            steps {
                withCredentials([string(credentialsId: 'sonarcloud-token', variable: 'SONAR_TOKEN')]) {
                    script {
                        docker.image('sonarsource/sonar-scanner-cli:latest').inside {
                            sh 'sonar-scanner'
                        }
                    }
                }
            }
        }

        stage('Integration Tests') {
            when { anyOf { branch 'main'; branch 'feature/*' } }
            steps {
                sh "BACKEND_IMAGE=${env.BACKEND_IMAGE} docker compose up -d --build"

                timeout(time: 2, unit: 'MINUTES') {
                    waitUntil {
                        script {
                            sh(script: 'docker compose exec -T backend curl -sf http://frontend/api/health', returnStatus: true) == 0
                        }
                    }
                }

                script {
                    docker.image(env.BACKEND_IMAGE).inside('--network smartcart_frontend-net') {
                        sh 'pytest tests/integration_tests.py --no-cov'
                    }
                }
            }
        }

        stage('E2E Tests') {
            when { anyOf { branch 'main'; branch 'feature/*' } }
            steps {
                script {
                    docker.image('mcr.microsoft.com/playwright/python:v1.58.0-noble').inside('--network smartcart_frontend-net') {
                        sh 'pip install pytest playwright && TEST_BASE_URL=http://frontend python -m pytest tests/e2e_tests.py -v --tb=short -x -o addopts=""'
                    }
                }
            }
        }

        stage('Tag & Publish') {
            when { branch 'main' }
            parallel {
                stage('Git Tag') {
                    steps {
                        withCredentials([usernamePassword(credentialsId: 'GitLab PAT', usernameVariable: 'GIT_USER', passwordVariable: 'GIT_TOKEN')]) {
                            sh "git tag ${env.VERSION}"
                            sh "git push https://\${GIT_USER}:\${GIT_TOKEN}@gitlab.com/arielgabai/smartcart.git ${env.VERSION}"
                        }
                    }
                }
                stage('Publish to ECR') {
                    steps {
                        sh "aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${ECR_URL}"
                        script {
                            def image = docker.image(env.BACKEND_IMAGE)
                            image.push(env.VERSION)
                            image.push('latest')
                        }
                    }
                }
            }
        }

        stage('Deploy') {
            when { branch 'main' }
            parallel {
                stage('Deploy to GitOps') {
                    steps {
                        withCredentials([usernamePassword(credentialsId: 'GitLab PAT', usernameVariable: 'GIT_USER', passwordVariable: 'GIT_TOKEN')]) {
                            sh """
                                git clone https://\${GIT_USER}:\${GIT_TOKEN}@gitlab.com/arielgabai/smartcart-gitops.git
                                cd smartcart-gitops
                                sed -i '/repository: 043187663485.dkr.ecr.ap-south-1.amazonaws.com\\/smartcart\$/{ n; s/tag: ".*"/tag: "${env.VERSION}"/; }' smartcart/values.yaml
                                git config user.email "jenkins@ariel.com"
                                git config user.name "Ariel's Jenkins Bot"
                                git add smartcart/values.yaml
                                git commit -m "update backend image to ${env.VERSION}"
                                git push https://\${GIT_USER}:\${GIT_TOKEN}@gitlab.com/arielgabai/smartcart-gitops.git main
                            """
                        }
                    }
                }
                stage('Deploy Static to S3') {
                    steps {
                        sh "aws s3 sync frontend/static/ s3://${S3_BUCKET}/ --delete --region ${AWS_REGION}"
                        sh """
                            DIST_ID=\$(aws cloudfront list-distributions \
                                --query "DistributionList.Items[?contains(Aliases.Items, '${DOMAIN}')].Id" \
                                --output text)
                            aws cloudfront create-invalidation --distribution-id \$DIST_ID --paths '/*'
                        """
                    }
                }
            }
        }

    }

    post {
        always {
            sh 'docker compose down -v --remove-orphans || true'
            sh 'docker system prune -af --volumes || true'
            cleanWs()
            script {
                def colors = [SUCCESS: 'good', FAILURE: 'danger', ABORTED: 'warning']
                def version = env.VERSION ?: 'dev'
                slackSend(
                    color: colors[currentBuild.result] ?: 'warning',
                    message: "${currentBuild.result}: ${env.JOB_NAME} #${env.BUILD_NUMBER} (${version})"
                )
            }
        }
    }
}
